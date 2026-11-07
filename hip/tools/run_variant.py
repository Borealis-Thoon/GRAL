"""Run one B00-family GPU variant on the RX 9070 XT and record kernel times and output identity.

Usage: run_variant.py <name> <build> <case> [KEY=VALUE ...]
  KEY=VALUE pairs are SMOKE_* overrides passed to smoke_hip.py (e.g. SMOKE_INU_GPU_HIPRTC_EXTRA=..., SMOKE_RUNTIME=...).
Writes perf2/results.json (one entry per name) with kernel sums from gpu_metrics.jsonl, NMAE vs frozen CPU/CUDA,
and GRZ member identity against perf2/reference/<case>.json (member hashes of the current HIP baseline output).
"""
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

PERF2 = Path(__file__).resolve().parent
JOB = PERF2.parent
PY = r'<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'


def members(folder):
    out = {}
    for grz in sorted(folder.glob('*.grz')):
        with zipfile.ZipFile(grz) as z:
            for n in z.namelist():
                out[grz.name + '/' + n] = hashlib.sha256(z.read(n)).hexdigest()
    return out


def main():
    name, build, case = sys.argv[1], sys.argv[2], sys.argv[3]
    overrides = dict(a.split('=', 1) for a in sys.argv[4:])
    results_path = PERF2 / 'results.json'
    results = json.loads(results_path.read_text(encoding='utf8')) if results_path.exists() else {}
    label = f'p2_{name}'
    env = {k: v for k, v in os.environ.items() if not k.startswith('SMOKE_')}
    env.update(overrides)
    proc = subprocess.run([PY, '-X', 'utf8', '-B', str(JOB / 'smoke_hip.py'), 'gpu', label, build, case + '_fixed00'], env=env,
                          capture_output=True, text=True, encoding='utf8', errors='replace')
    tgt = JOB / 'smoke' / label
    s = json.loads((tgt / 'smoke_result.json').read_text(encoding='utf8')) if (tgt / 'smoke_result.json').exists() else {}
    mpath = tgt / 'logs' / 'gpu_metrics.jsonl'
    mets = [json.loads(l) for l in open(mpath, encoding='utf8')] if mpath.exists() else []
    out = members(tgt / 'Computation') if (tgt / 'Computation').exists() else {}
    ref_path = PERF2 / 'reference' / f'{case}.json'
    ident = None
    if out and ref_path.exists():
        ref = json.loads(ref_path.read_text(encoding='utf8'))
        diff = sorted(k for k in set(ref) | set(out) if ref.get(k) != out.get(k))
        ident = {'members': len(ref), 'differing': len(diff), 'first_differing': diff[:8]}
    res0 = (mets[0].get('result_server_metrics') or {}) if mets else {}
    rec = {'case': case, 'build': build, 'overrides': overrides, 'rc': s.get('rc'), 'wall_s': s.get('wall_s'),
           'stdout_tail': proc.stdout[-400:] if proc.returncode else None,
           'fallback': s.get('gpu_fallback_lines'),
           'situations': len(mets),
           'fresh_kernel_s': round(sum(m.get('fresh_kernel_ms') or 0 for m in mets) / 1000, 3),
           'residual_kernel_s': round(sum(m.get('residual_kernel_ms') or 0 for m in mets) / 1000, 3),
           'elapsed_s': round(sum(m.get('elapsed_s') or 0 for m in mets), 3),
           'per_situation_fresh_ms': [round(m.get('fresh_kernel_ms') or 0, 1) for m in mets],
           'resources': res0.get('kernel_resources'),
           'nmae_vs_cpu': (s.get('vs_frozen_cpu') or {}).get('con_nmae_pooled'),
           'nmae_vs_cuda': (s.get('vs_frozen_gpu') or {}).get('con_nmae_pooled'),
           'bias_vs_cpu': (s.get('vs_frozen_cpu') or {}).get('con_bias_pooled'),
           'identity_vs_reference': ident}
    results[name] = rec
    results_path.write_text(json.dumps(results, indent=1), encoding='utf8')
    if name.startswith('ref_') and out:
        ref_path.parent.mkdir(exist_ok=True)
        ref_path.write_text(json.dumps(out, indent=0), encoding='utf8')
    print(json.dumps({k: v for k, v in rec.items() if k != 'per_situation_fresh_ms'}, indent=1))


if __name__ == '__main__':
    main()
