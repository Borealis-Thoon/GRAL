"""Backend-selection, cache, mapped-host and trap tests of a PR build on the Radeon-only PC0 (no nvcuda.dll installed).

Each case runs B00 (fixed seed 00) through smoke_hip.py and records the return code, the GPU console lines, the last
lines of the GPU runtime log, the module-cache status and, where a reference is given, how many GRZ members are
byte-identical to it.
  auto_cold      INU_GPU_BACKEND unset, empty cache folder          -> HIP, identical to the earlier HIP build
  hip_upper      INU_GPU_BACKEND=' HIP ', same cache folder         -> HIP, cache hit, identical
  cuda           INU_GPU_BACKEND=cuda                               -> startup failure naming nvcuda.dll
  cuda_fallback  INU_GPU_BACKEND=cuda, INU_GPU_FALLBACK_ON_STARTUP=1 -> CPU run, identical to the frozen CPU output
  bogus          INU_GPU_BACKEND=bogus                              -> startup failure naming cuda or hip
  device1        INU_GPU_BACKEND=hip, INU_GPU_DEVICE=1              -> out-of-range failure in HIP wording
  runtime_missing INU_GPU_BACKEND=hip, INU_GPU_HIP_RUNTIME=<missing> -> startup failure naming the file
  no_comgr       hiprtc folder without amd_comgr*.dll               -> startup failure naming amd_comgr
  mapped_host    INU_GPU_MEMORY_BUDGET_BYTES=16 MiB (B00 peak ~60 MiB) -> arrays in mapped host memory, identical
  trap           kernel with a forced trap at particle 1000         -> error reported, run stops (no hang)
Usage: backend_tests2.py <build> <out json> [case,case,...]
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

JOB = Path(__file__).resolve().parent
PY = r'<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
FV = Path(r'<jobs>\20261103_gral_gpu_final_validation\runs\final448_001\targets')
HIPRTC = Path(r'<user>\AppData\Local\rocm-sdk\venv-10.1\Lib\site-packages\_rocm_sdk_core\bin')
build, out = sys.argv[1], Path(sys.argv[2])
only = sys.argv[3].split(',') if len(sys.argv) > 3 else None
RT = JOB / 'pr77_hip' / 'gpu' / 'runtime'
TESTS = JOB / 'tests' / Path(build).name
TESTS.mkdir(parents=True, exist_ok=True)
HIP_REF = JOB / 'smoke' / 'B00_fixed00_build_hip3' / 'Computation'
CPU_REF = FV / 'B00_fixed00_cpu' / 'Computation'

# Fixtures: a hiprtc folder without comgr, and a runtime folder whose kernel traps at particle 1000.
nocomgr = TESTS / 'hiprtc_nocomgr'
nocomgr.mkdir(exist_ok=True)
for name in ('hiprtc0716.dll', 'hiprtc-builtins0716.dll'):
    shutil.copyfile(HIPRTC / name, nocomgr / name)
trap_rt = TESTS / 'runtime_trap'
trap_rt.mkdir(exist_ok=True)
shutil.copyfile(RT / 'fields_manifest.json', trap_rt / 'fields_manifest.json')
src = (RT / 'generated.cu').read_text(encoding='utf8')
old = 'if(q<count){Zeitschleife_Calculate(first+q);}'
assert src.count(old) == 1, 'gral_fresh body not found once'
(trap_rt / 'generated.cu').write_text(src.replace(old, 'if(q<count){if(first+q==1000)asm("trap;");Zeitschleife_Calculate(first+q);}'),
                                       encoding='utf8', newline='\n')
cache = TESTS / 'module_cache'
if not only or 'auto_cold' in only:
    shutil.rmtree(cache, ignore_errors=True)
cache.mkdir(exist_ok=True)

CASES = [
    ('auto_cold', {'SMOKE_BACKEND': 'auto', 'SMOKE_INU_GPU_CACHE_DIR': str(cache)}, HIP_REF),
    ('hip_upper', {'SMOKE_BACKEND': ' HIP ', 'SMOKE_INU_GPU_CACHE_DIR': str(cache)}, HIP_REF),
    ('cuda', {'SMOKE_BACKEND': 'cuda'}, None),
    ('cuda_fallback', {'SMOKE_BACKEND': 'cuda', 'SMOKE_FALLBACK': '1'}, CPU_REF),
    ('bogus', {'SMOKE_BACKEND': 'bogus'}, None),
    ('device1', {'SMOKE_BACKEND': 'hip', 'SMOKE_INU_GPU_DEVICE': '1'}, None),
    ('runtime_missing', {'SMOKE_BACKEND': 'hip', 'SMOKE_INU_GPU_HIP_RUNTIME': str(TESTS / 'missing' / 'amdhip64_7.dll')}, None),
    ('no_comgr', {'SMOKE_BACKEND': 'hip', 'SMOKE_HIPRTC_DIR': str(nocomgr)}, None),
    ('mapped_host', {'SMOKE_BACKEND': 'hip', 'SMOKE_INU_GPU_MEMORY_BUDGET_BYTES': str(16 * 1024 * 1024),
                     'SMOKE_INU_GPU_CACHE_DIR': str(cache)}, HIP_REF),
    ('trap', {'SMOKE_BACKEND': 'hip', 'SMOKE_RUNTIME': str(trap_rt), 'SMOKE_TIMEOUT': '600',
              'SMOKE_INU_GPU_CACHE_DIR': 'off'}, None),
]


def members(folder):
    res = {}
    for g in sorted(Path(folder).glob('*.grz')):
        with zipfile.ZipFile(g) as z:
            for n in z.namelist():
                res[g.name + '/' + n] = hashlib.sha256(z.read(n)).hexdigest()
    return res


res = json.loads(out.read_text(encoding='utf8')) if out.exists() else {}
for name, extra, ref in CASES:
    if only and name not in only:
        continue
    label = f'bt2_{name}_{Path(build).name}'
    tgt = JOB / 'smoke' / label
    shutil.rmtree(tgt, ignore_errors=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith('SMOKE_')}
    env['SMOKE_RUNTIME'] = str(RT)
    env.update(extra)
    p = subprocess.run([PY, '-X', 'utf8', '-B', str(JOB / 'smoke_hip.py'), 'gpu', label, build, 'B00_fixed00'], env=env,
                       capture_output=True, text=True, encoding='utf8', errors='replace')
    s = json.loads((tgt / 'smoke_result.json').read_text(encoding='utf8')) if (tgt / 'smoke_result.json').exists() else {}
    stdout = (tgt / 'logs' / 'stdout.log').read_bytes().decode('utf8', 'replace') if (tgt / 'logs' / 'stdout.log').exists() else ''
    stderr_log = tgt / 'logs' / 'gpu_server.stderr'
    log_tail = stderr_log.read_bytes().decode('utf8', 'replace').splitlines()[-4:] if stderr_log.exists() else []
    metrics = tgt / 'logs' / 'gpu_metrics.jsonl'
    rows = [json.loads(l).get('result_server_metrics') or {} for l in metrics.read_text(encoding='utf8').splitlines()] if metrics.exists() else []
    r = {'rc': s.get('rc'), 'timed_out': s.get('timed_out'), 'wall_s': s.get('wall_s'), 'dll_sha256': s.get('dll_sha256'),
         'gpu_console_lines': [l[:400] for l in stdout.splitlines() if 'GPU' in l][:4], 'gpu_log_tail': [l[:400] for l in log_tail],
         'situations_with_metrics': len(rows),
         'cache_status': rows[0].get('cache_status') if rows else None,
         'cache_write_status': rows[0].get('cache_write_status') if rows else None,
         'peak_device_buffer_bytes': max((m.get('peak_device_buffer_bytes') or 0 for m in rows), default=None),
         'peak_mapped_host_bytes': max((m.get('peak_mapped_host_bytes') or 0 for m in rows), default=None),
         'mapped_buffer_names': sorted({n for m in rows for n in (m.get('mapped_buffer_names') or [])}),
         'harness_error': p.stderr[-600:] if not s else None}
    if ref is not None and s.get('rc') == 0:
        a, b = members(ref), members(tgt / 'Computation')
        r['grz_identical_to_reference'] = f"{sum(1 for k in a if b.get(k) == a[k])}/{len(a)}"
        r['reference'] = str(ref)
    res[name] = r
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf8')
    print(name, json.dumps(r, ensure_ascii=False)[:700], flush=True)
