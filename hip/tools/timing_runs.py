"""Same-session wall times: HIP GPU (RX 9070 XT) vs CPU path (CPUs 0-15), alternating, for a few study cases.

Usage: timing_runs.py <build> <out json> <cases comma list> [repeats=2]
Each run goes through smoke_hip.py (inputs copied from the frozen study, Job Object on CPUs 0-15).
"""
import json, subprocess, sys
from pathlib import Path

JOB = Path(__file__).resolve().parent
PY = r'<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
build, out, cases = sys.argv[1], Path(sys.argv[2]), sys.argv[3].split(',')
reps = int(sys.argv[4]) if len(sys.argv) > 4 else 2
res = json.loads(out.read_text(encoding='utf8')) if out.exists() else []
for case in cases:
    for r in range(reps):
        for mode in ('gpu', 'cpu'):
            label = f'time_{case}_{mode}_r{r}_{Path(build).name}'
            if any(x['label'] == label for x in res):
                continue
            subprocess.run([PY, '-X', 'utf8', '-B', str(JOB / 'smoke_hip.py'), mode, label, build, f'{case}_fixed00'],
                           capture_output=True, text=True, encoding='utf8', errors='replace')
            f = JOB / 'smoke' / label / 'smoke_result.json'
            s = json.loads(f.read_text(encoding='utf8')) if f.exists() else {}
            row = {'label': label, 'case': case, 'mode': mode, 'rep': r, 'rc': s.get('rc'), 'wall_s': s.get('wall_s'),
                   'nmae_vs_frozen_cpu': (s.get('vs_frozen_cpu') or {}).get('con_nmae_pooled'),
                   'fallback': s.get('gpu_fallback_lines')}
            res.append(row)
            out.write_text(json.dumps(res, indent=1), encoding='utf8')
            print(json.dumps(row), flush=True)
