"""Run the HIP build on every study case (one fixed seed) and compare with the frozen CPU and CUDA outputs.

For each case X: HIP run of X_fixed<seed>_gpu inputs, then pooled .con NMAE / bias / min-hour Jaccard against
  X_fixed<seed>_cpu (frozen CPU) and X_fixed<seed>_gpu (frozen CUDA, RTX 5080),
plus the study baselines: frozen CPU vs CUDA (same seed) and frozen CPU seed pair (fixed<seed> vs fixed<seed+1>).
Usage: validate_cases.py <build folder> <out json> [seed=00] [cases comma list]
"""
import json, subprocess, sys, time
from pathlib import Path

JOB = Path(__file__).resolve().parent
PY = r'<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
sys.path.insert(0, str(JOB))
import baseline_nmae  # noqa: E402  (defines run(a, b) over frozen targets)

T = Path(r'<jobs>\20261103_gral_gpu_final_validation\runs\final448_001\targets')
build, out = sys.argv[1], Path(sys.argv[2])
seed = sys.argv[3] if len(sys.argv) > 3 else '00'
cases = sys.argv[4].split(',') if len(sys.argv) > 4 else sorted({p.name.split('_')[0] for p in T.glob('*_fixed00_gpu')})
nxt = f'{int(seed) + 1:02d}'
results = json.loads(out.read_text(encoding='utf8')) if out.exists() else {}
for case in cases:
    if case in results and results[case].get('hip'):
        continue
    label = f'{case}_fixed{seed}_{Path(build).name}'
    t0 = time.time()
    p = subprocess.run([PY, '-X', 'utf8', '-B', str(JOB / 'smoke_hip.py'), 'gpu', label, build, f'{case}_fixed{seed}'],
                       capture_output=True, text=True, encoding='utf8', errors='replace')
    res_file = JOB / 'smoke' / label / 'smoke_result.json'
    hip = json.loads(res_file.read_text(encoding='utf8')) if res_file.exists() else {'error': p.stderr[-1500:]}
    entry = {'hip': {k: hip.get(k) for k in ('rc', 'wall_s', 'gpu_fallback_lines', 'gpu_device_line', 'vs_frozen_cpu', 'vs_frozen_gpu', 'error')}}
    try:
        entry['baseline_cpu_vs_cuda'] = baseline_nmae.run(f'{case}_fixed{seed}_cpu', f'{case}_fixed{seed}_gpu')
        entry['baseline_cpu_seed_pair'] = baseline_nmae.run(f'{case}_fixed{seed}_cpu', f'{case}_fixed{nxt}_cpu')
    except Exception as e:  # noqa: BLE001
        entry['baseline_error'] = repr(e)[:500]
    results[case] = entry
    out.write_text(json.dumps(results, indent=1), encoding='utf8')
    h = entry['hip']
    c = (h.get('vs_frozen_cpu') or {}).get('con_nmae_pooled'); g = (h.get('vs_frozen_gpu') or {}).get('con_nmae_pooled')
    b = (entry.get('baseline_cpu_vs_cuda') or {}).get('con_nmae_pooled'); s = (entry.get('baseline_cpu_seed_pair') or {}).get('con_nmae_pooled')
    print(f'{case} rc={h.get("rc")} wall={h.get("wall_s")} hip_vs_cpu={c} hip_vs_cuda={g} cuda_vs_cpu={b} seed_pair={s} ({time.time()-t0:.0f}s)', flush=True)
