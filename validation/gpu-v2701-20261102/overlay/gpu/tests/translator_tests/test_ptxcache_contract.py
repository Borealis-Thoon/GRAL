"""CPU-only PTX cache persistence and startup fallback contracts."""
import base64
from concurrent.futures import ThreadPoolExecutor
import ctypes
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from test_runtime_contract import server

cache = server.ptx_cache


class PtxCacheContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gral-ptx-contract-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'cache' / 'entry.json'
        self.key = 'a' * 64
        self.ptx = b'// exact PTX\n.version 8.0\n\0'

    def test_cache_is_disabled_without_explicit_local_directory(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cache.cache_path({'source': 'abc'}), (None, 'disabled'))
        for directory in ('relative', r'\\server\share\cache'):
            with self.subTest(directory=directory), patch.dict(os.environ, INU_GPU_CACHE_DIR=directory):
                self.assertEqual(cache.cache_path({}), (None, 'invalid_directory'))
        with patch.dict(os.environ, INU_GPU_CACHE_DIR=self.temp.name), patch.object(ctypes.windll.kernel32, 'GetDriveTypeW', return_value=4):
            self.assertEqual(cache.cache_path({}), (None, 'invalid_directory'))

    def test_key_is_order_independent_but_changes_for_each_identity_component(self):
        identity = {'source': 'abc', 'manifest': 'def', 'abi': {'offset': 8}, 'options': ['--fmad=false'], 'nvrtc': '12.9'}
        with patch.dict(os.environ, INU_GPU_CACHE_DIR=self.temp.name), patch.object(ctypes.windll.kernel32, 'GetDriveTypeW', return_value=3):
            path, key = cache.cache_path(identity)
            self.assertEqual((path, key), cache.cache_path(dict(reversed(list(identity.items())))))
            for field in identity:
                changed = dict(identity, **{field: 'changed'})
                self.assertNotEqual(key, cache.cache_path(changed)[1], field)
            self.assertEqual(path.name, key + '.json')
            self.assertEqual(path.parent, Path(self.temp.name).resolve())

    def test_miss_write_hit_preserves_exact_null_terminated_ptx(self):
        self.assertEqual(cache.read(self.path, self.key), (None, 'miss'))
        self.assertEqual(cache.write(self.path, self.key, self.ptx), 'written')
        self.assertEqual(cache.read(self.path, self.key), (self.ptx, 'hit'))
        self.assertEqual(list(self.path.parent.glob('.ptx-*.tmp')), [])

    def test_corrupt_entries_are_misses_with_read_error(self):
        cache.write(self.path, self.key, self.ptx)
        good = json.loads(self.path.read_text())
        mutations = [None, [], dict(good, schema=True), dict(good, schema=2), dict(good, key='wrong'),
                     dict(good, size=True), dict(good, size=1), dict(good, size=len(self.ptx)+1),
                     dict(good, sha256='bad'), dict(good, ptx='!invalid!'),
                     dict(good, ptx=base64.b64encode(b'\0x\0').decode(), size=3, sha256=cache.digest(b'\0x\0')),
                     dict(good, ptx=base64.b64encode(b'no-null').decode(), size=7, sha256=cache.digest(b'no-null')),
                     {k: v for k, v in good.items() if k != 'ptx'}]
        for entry in mutations:
            with self.subTest(entry=entry):
                self.path.write_text(json.dumps(entry))
                self.assertEqual(cache.read(self.path, self.key), (None, 'read_error'))
        self.path.write_bytes(b'{broken-json\xff')
        self.assertEqual(cache.read(self.path, self.key), (None, 'read_error'))

    def test_ptx_size_and_entry_read_limits_reject_without_large_allocations(self):
        with patch.object(cache, 'MAX_PTX', 8):
            for ptx in (b'', b'\0', b'no-terminator', b'x\0y\0', b'12345678\0'):
                with self.subTest(ptx=ptx):
                    self.assertEqual(cache.write(self.path, self.key, ptx), 'write_error')
            self.assertEqual(cache.write(self.path, self.key, b'1234567\0'), 'written')
            self.assertEqual(cache.read(self.path, self.key), (b'1234567\0', 'hit'))
            entry = json.loads(self.path.read_text()); entry['size'] = 9
            self.path.write_text(json.dumps(entry))
            self.assertEqual(cache.read(self.path, self.key), (None, 'read_error'))
        with patch.object(cache, 'MAX_ENTRY', 8):
            self.path.write_bytes(b' ' * 9)
            self.assertEqual(cache.read(self.path, self.key), (None, 'read_error'))

    def test_failed_atomic_replace_keeps_previous_entry_and_cleans_temporary_file(self):
        cache.write(self.path, self.key, self.ptx)
        before = self.path.read_bytes()
        with patch.object(cache.os, 'replace', side_effect=OSError('locked')):
            self.assertEqual(cache.write(self.path, self.key, b'new\0'), 'write_error')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('.ptx-*.tmp')), [])

    def test_parallel_writers_publish_only_complete_valid_entries(self):
        payloads = [('// worker ' + str(i) + '\n' + 'x'*4096).encode() + b'\0' for i in range(16)]
        cache.write(self.path, self.key, payloads[0])
        barrier = threading.Barrier(4)
        def worker(index):
            barrier.wait()
            statuses = []
            for payload in payloads[index::4]:
                statuses.append(cache.write(self.path, self.key, payload))
                ptx, status = cache.read(self.path, self.key)
                self.assertIn(status, ('hit', 'read_error'))
                if status == 'hit':
                    self.assertIn(ptx, payloads)
                else:
                    self.assertIsNone(ptx)
            return statuses
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(worker, range(4)))
        self.assertTrue(all(status in ('written', 'write_error') for group in statuses for status in group))
        self.assertIn('written', [status for group in statuses for status in group])
        self.assertIn(cache.read(self.path, self.key)[0], payloads)
        self.assertEqual(list(self.path.parent.glob('.ptx-*.tmp')), [])

    def startup(self, cached, fail_cached=False, fail_compile=False, identity_error=False):
        root = Path(self.temp.name)
        (root/'generated.cu').write_text('// source')
        for name in ('nvrtc.dll', 'builtins.dll'):
            (root/name).write_bytes(name.encode())
        class FakeCuda:
            def __init__(self):
                self.context_ms = 1.0; self.modules = []; self.events = []
                self.nvrtc_path = root/'nvrtc.dll'; self.nvrtc_builtins_path = root/'builtins.dll'
                self.nvrtc_version = (12, 9); self.compiles = 0; self.closed = False
            def compile_ptx(self, source):
                self.compiles += 1
                if fail_compile: raise RuntimeError('compiler failed')
                return b'compiled\0', 'compile log'
            def event_create(self, *args): return 0
            def check(self, code, operation):
                if code: raise RuntimeError(operation)
            def close(self): self.closed = True
        cuda = FakeCuda(); loads = []
        def load(item, ptx):
            loads.append(ptx); item.module = None
            if fail_cached and ptx == cached: raise ValueError('ABI mismatch')
            item.module = object(); item.cuda.modules.append(item.module)
        identities = []
        def path(identity):
            identities.append(identity)
            if identity_error: raise OSError('DLL unavailable')
            return self.path, self.key
        with patch.dict(os.environ, INU_GPU_CACHE_DIR=self.temp.name), patch.object(server, 'ROOT', root), \
             patch.object(server, 'Cuda', return_value=cuda), patch.object(server.Server, 'load_and_validate', load), \
             patch.object(cache, 'cache_path', side_effect=path), patch.object(cache, 'read', return_value=(cached, 'hit' if cached else 'miss')), \
             patch.object(cache, 'write', return_value='written') as write, patch.object(server.sys, 'stderr', io.StringIO()):
            if fail_compile:
                with self.assertRaisesRegex(RuntimeError, 'compiler failed'): server.Server()
                self.assertTrue(cuda.closed)
                write.assert_not_called()
                return
            item = server.Server()
            return item, cuda, loads, write.call_count, identities[0]

    def test_valid_startup_cache_hit_skips_nvrtc_but_loads_and_checks_abi(self):
        item, cuda, loads, writes, identity = self.startup(b'cached\0')
        self.assertEqual((cuda.compiles, loads, writes), (0, [b'cached\0'], 0))
        self.assertEqual(item.metrics['cache_status'], 'hit')
        for field in ('source_sha256', 'manifest_sha256', 'state_size', 'state_alignment', 'fields', 'options', 'program', 'nvrtc_version', 'nvrtc_sha256', 'nvrtc_builtins_sha256'):
            self.assertIn(field, identity)
        self.assertEqual(identity['state_size'], ctypes.sizeof(server.State))
        self.assertIn('--fmad=false', identity['options'])

    def test_rejected_cached_module_recompiles_and_revalidates_before_write(self):
        item, cuda, loads, writes, _ = self.startup(b'cached\0', fail_cached=True)
        self.assertEqual((cuda.compiles, loads, writes), (1, [b'cached\0', b'compiled\0'], 1))
        self.assertEqual(item.metrics['cache_status'], 'hit_rejected')
        self.assertEqual(item.metrics['cache_write_status'], 'written')

    def test_rejected_module_is_unloaded_before_error_propagates(self):
        item = object.__new__(server.Server)
        item.metrics = {'module_load_ms': 0.0, 'post_load_abi_ms': 0.0}
        module = object()
        from unittest.mock import Mock
        item.cuda = types.SimpleNamespace(load_ptx=Mock(return_value=module), unload_module=Mock())
        item.function = Mock(return_value='size-kernel')
        item.validate_module = Mock(side_effect=ValueError('ABI mismatch'))
        with self.assertRaisesRegex(ValueError, 'ABI mismatch'):
            item.load_and_validate(b'valid-ptx\0')
        item.cuda.unload_module.assert_called_once_with(module)
        item.function.assert_called_once_with('gral_state_size')

    def test_cache_miss_compiles_and_writes_once(self):
        item, cuda, loads, writes, _ = self.startup(None)
        self.assertEqual((cuda.compiles, loads, writes), (1, [b'compiled\0'], 1))
        self.assertEqual(item.metrics['cache_status'], 'miss')

    def test_identity_failure_falls_back_to_compile_without_cache_write(self):
        item, cuda, loads, writes, _ = self.startup(None, identity_error=True)
        self.assertEqual((cuda.compiles, loads, writes), (1, [b'compiled\0'], 0))
        self.assertEqual(item.metrics['cache_status'], 'identity_error')

    def test_compile_failure_closes_cuda_and_never_publishes_cache(self):
        self.startup(None, fail_compile=True)


if __name__ == '__main__':
    unittest.main()
