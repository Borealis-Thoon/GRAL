"""CPU-only dispatch plans: no CUDA context or particle-sized allocation."""
import ctypes
import types
import unittest
from unittest.mock import Mock, patch

from test_runtime_contract import server


I32_MAX = 2**31 - 1
PARTICLE_ARRAYS = ('SourceType', 'Xcoord', 'YCoord', 'ZCoord', 'ParticleMass',
                   'ParticleSG', 'ParticleSource', 'ParticleMode', 'ParticleVdep', 'ParticleVsed')
RESIDUAL_ARRAYS = ('_resI', '_resJ', '_resK', '_resSG', '_resConc', '_resSplit')


class DispatchContract(unittest.TestCase):
    def make_server(self, length=100000002, residual_count=0):
        item = object.__new__(server.Server)
        item.state = server.State()
        item.state_address = ctypes.c_uint64(1)
        item.descriptors = {}
        item.buffers = {}
        item.metrics = {'state_d2h_ms': 0.0, 'state_d2h_bytes': 0}
        item.phase_counts = {'fresh': 0, 'residual': 0}
        item.residual_trace_base = 0
        item.guard = Mock()
        item.bind = Mock()
        item.launch = Mock(return_value=0.0)
        item.cuda = types.SimpleNamespace(check=lambda *_: None, d2h=lambda *_: 0)
        for name in PARTICLE_ARRAYS:
            array = getattr(item.state, name)
            array.p = 4096
            array.d[0] = length
        for name in RESIDUAL_ARRAYS:
            item.descriptors[name] = {'shape': [residual_count], 'is_null': False}
            item.buffers[name] = (ctypes.c_uint64(4096), residual_count * 4)
        item.fn_fresh = 'fresh'
        item.fn_residual = 'residual'
        return item

    def header(self, count, first=1, phase='fresh', chunk=65536):
        return {'count': count, 'first': first, 'phase': phase,
                'chunk': chunk, 'block': 128, 'payload_bytes': 0}

    def test_over_100_million_uses_bounded_contiguous_chunks(self):
        count = 100000001
        item = self.make_server(count + 1)
        result = item.execute(self.header(count, chunk=I32_MAX))
        next_first = 1
        for call in item.launch.call_args_list:
            function, part, args, block = call.args
            self.assertEqual(function, 'fresh')
            self.assertEqual(block, 128)
            self.assertTrue(0 < part <= 65536)
            self.assertEqual([arg.value for arg in args], [next_first, part])
            next_first += part
        self.assertEqual(next_first, count + 1)
        self.assertEqual(result['count'], count)
        self.assertEqual(item.phase_counts['fresh'], count)
        self.assertEqual(item.launch.call_count, (count + 65535) // 65536)

    def test_count_and_first_require_strict_int32(self):
        for field, values in (('count', (True, False, 1.0, '1', None, -1, I32_MAX + 1)),
                              ('first', (True, False, 1.0, '1', None, -1, I32_MAX + 1))):
            for phase in ('fresh', 'residual'):
                for value in values:
                    with self.subTest(field=field, phase=phase, value=value):
                        item = self.make_server(residual_count=1)
                        header = self.header(1, phase=phase)
                        header[field] = value
                        with self.assertRaises(ValueError):
                            item.execute(header)
                        item.bind.assert_not_called()
                        item.launch.assert_not_called()

    def test_all_particle_arrays_bound_the_fresh_range(self):
        for name in PARTICLE_ARRAYS:
            for bad_pointer in (False, True):
                with self.subTest(array=name, bad_pointer=bad_pointer):
                    item = self.make_server(5)
                    array = getattr(item.state, name)
                    if bad_pointer:
                        array.p = 0
                    else:
                        array.d[0] = 4
                    with self.assertRaisesRegex(ValueError, name):
                        item.execute(self.header(4))
                    item.bind.assert_not_called()
                    item.launch.assert_not_called()

    def test_fresh_int32_boundary_and_zero_count(self):
        item = self.make_server(I32_MAX)
        item.execute(self.header(1, first=I32_MAX - 1))
        self.assertEqual(item.launch.call_args.args[2][0].value, I32_MAX - 1)
        item.launch.reset_mock()
        item.execute(self.header(0, first=I32_MAX))
        item.launch.assert_not_called()
        for first, count in ((0, 1), (I32_MAX, 1), (1, I32_MAX)):
            with self.subTest(first=first, count=count):
                with self.assertRaises(ValueError):
                    item.execute(self.header(count, first=first))

    def test_residual_int32_max_count_plan_has_no_wrapped_arguments(self):
        item = self.make_server(residual_count=I32_MAX)
        item.execute(self.header(I32_MAX, first=0, phase='residual'))
        offset = 0
        for call in item.launch.call_args_list:
            function, part, args, _ = call.args
            self.assertEqual(function, 'residual')
            self.assertTrue(0 < part <= 65536)
            self.assertEqual([arg.value for arg in args[:2]], [part, offset])
            self.assertEqual([arg.value for arg in args[2:]], [4096 + offset * 4] * 6)
            offset += part
        self.assertEqual(offset, I32_MAX)
        self.assertEqual(item.residual_trace_base, I32_MAX)

    def test_residual_trace_range_rejects_overflow_before_launch(self):
        for base in (True, 1.0, -1, I32_MAX - 1, I32_MAX + 1):
            with self.subTest(base=base):
                item = self.make_server(residual_count=2)
                item.residual_trace_base = base
                with self.assertRaisesRegex(ValueError, '[Rr]esidual.*trace'):
                    item.execute(self.header(2, first=0, phase='residual'))
                item.bind.assert_not_called()
                item.launch.assert_not_called()
        item = self.make_server(residual_count=2)
        item.residual_trace_base = I32_MAX - 2
        item.execute(self.header(2, first=0, phase='residual'))
        self.assertEqual(item.residual_trace_base, I32_MAX)

    def test_residual_descriptor_and_buffer_must_cover_count(self):
        for name in RESIDUAL_ARRAYS:
            for fault in ('shape', 'null', 'bytes', 'pointer', 'missing'):
                with self.subTest(array=name, fault=fault):
                    item = self.make_server(residual_count=2)
                    if fault == 'shape':
                        item.descriptors[name]['shape'] = [1]
                    elif fault == 'null':
                        item.descriptors[name]['is_null'] = True
                    elif fault == 'bytes':
                        item.buffers[name] = (ctypes.c_uint64(4096), 4)
                    elif fault == 'pointer':
                        item.buffers[name] = (ctypes.c_uint64(0), 8)
                    else:
                        del item.buffers[name]
                    with self.assertRaisesRegex(ValueError, name):
                        item.execute(self.header(2, first=0, phase='residual'))
                    item.bind.assert_not_called()
                    item.launch.assert_not_called()

    def test_array_dimensions_must_fit_signed_int32_before_payload_read(self):
        item = self.make_server()
        for length in (True, False, 1.0, -1, I32_MAX + 1):
            with self.subTest(length=length):
                header = {'payload_bytes': max(0, int(length)), 'arrays': [
                    {'name': 'SourceType', 'dtype': 'Byte', 'shape': [length],
                     'is_null': False, 'bytes': max(0, int(length)), 'offset': 0}]}
                with patch.object(server, 'read_exact', side_effect=AssertionError('Payload read')):
                    with self.assertRaisesRegex(ValueError, 'shape'):
                        item.receive(header)


if __name__ == '__main__':
    unittest.main()
