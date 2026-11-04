"""Compile target PTX and test two Server startups in a temporary runtime copy.

Usage: python rerun_compat.py CHECKOUT [--nvrtc-dir ABSOLUTE_DIR]
Requires Windows, a compatible NVIDIA driver/device and NVRTC. No model data.
The target matrix is compilation only; startup uses the actual local GPU.
"""
import argparse
import ctypes
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

TARGETS = (50, 52, 60, 70, 75, 86, 89, 120)


def worker(runtime, mode):
    sys.path.insert(0, str(runtime))
    if mode == 'matrix':
        common = importlib.import_module('cuda_common')
        cuda = common.Cuda()
        try:
            source = (runtime / 'generated.cu').read_text(encoding='utf-8')
            rows = []
            for target in TARGETS:
                try:
                    cuda.nvrtc_options = common._options_for_arch(target)
                    ptx, _ = cuda.compile_ptx(source)
                    rows.append({'target': target, 'status': 'pass', 'bytes': len(ptx),
                                 'sha256': hashlib.sha256(ptx).hexdigest()})
                except Exception as exc:
                    rows.append({'target': target, 'status': 'fail', 'error': str(exc)})
            return {'targets': rows, 'status': 'pass' if all(x['status'] == 'pass' for x in rows) else 'fail'}
        finally:
            cuda.close()
    server_module = importlib.import_module('server')
    server = server_module.Server()
    try:
        py_size = ctypes.sizeof(server_module.State)
        cuda_size = server.state_bytes.value
        metrics = server.metrics
        return {'status': 'pass' if py_size == cuda_size else 'fail',
                'python_state_bytes': py_size, 'cuda_state_bytes': cuda_size,
                'cache_status': metrics.get('cache_status'),
                'cache_write_status': metrics.get('cache_write_status'),
                'nvrtc_compile_ms': metrics.get('nvrtc_compile_ms')}
    finally:
        server.cuda.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path, help='PR checkout root')
    parser.add_argument('--nvrtc-dir', type=Path, help='absolute directory containing compatible NVRTC DLLs')
    parser.add_argument('--worker', choices=('matrix', 'startup'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        try:
            result = worker(args.checkout, args.worker)
        except Exception as exc:
            result = {'status': 'fail', 'error': str(exc)}
        print(json.dumps(result))
        return 0 if result['status'] == 'pass' else 1
    source = args.checkout.resolve() / 'gpu' / 'runtime'
    if not (source / 'generated.cu').is_file():
        parser.error('checkout must contain gpu/runtime/generated.cu')
    if args.nvrtc_dir and not args.nvrtc_dir.is_absolute():
        parser.error('--nvrtc-dir must be absolute')
    with tempfile.TemporaryDirectory(prefix='gral_compat_') as temp:
        root = Path(temp)
        runtime = root / 'runtime'
        shutil.copytree(source, runtime, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        env = os.environ.copy()
        for key in ('INU_GPU_MAX_SLICES', 'INU_GPU_MAX_RECEPTORS', 'INU_GPU_MEMORY_BUDGET_BYTES', 'INU_GPU_MEMORY_RESERVE_BYTES'):
            env.pop(key, None)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['INU_GPU_CACHE_DIR'] = str(root / 'cache')
        env['CUDA_CACHE_PATH'] = str(root / 'cuda-cache')
        if args.nvrtc_dir:
            env['INU_GPU_NVRTC_DIR'] = str(args.nvrtc_dir)
        results = {}
        for label, mode in (('matrix', 'matrix'), ('cold', 'startup'), ('warm', 'startup')):
            proc = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), str(runtime), '--worker', mode],
                                  env=env, cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace')
            try:
                results[label] = json.loads(proc.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                results[label] = {'status': 'fail', 'error': proc.stderr or proc.stdout or 'worker produced no result'}
            results[label]['returncode'] = proc.returncode
        cold, warm = results['cold'], results['warm']
        results['cache_check'] = (cold.get('cache_status') == 'miss' and
                                  cold.get('cache_write_status') == 'written' and
                                  warm.get('cache_status') == 'hit' and warm.get('nvrtc_compile_ms') == 0.0)
        results['status'] = 'pass' if results['cache_check'] and all(results[k]['status'] == 'pass' and results[k]['returncode'] == 0 for k in ('matrix', 'cold', 'warm')) else 'fail'
        print(json.dumps(results, indent=2))
        return 0 if results['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
