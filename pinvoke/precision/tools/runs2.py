"""Run B00 cases with one build: CPU, the current double GPU kernel (D) and the precision variants.

Usage: runs2.py <label> <build folder> <case>:<variant> [...]
  case     B00 (frozen fixed-seed inputs at the synthetic origin), or a folder name under precision/cases (e.g. B00s)
  variant  cpu | D | D2 | M | F | M2 | F2  (D = wt/gpu/runtime, others = precision/rt_<variant>)
Outputs: smoke/<label>_<case>_<variant>; one JSON row per run in precision/runs2_<label>.jsonl. Runs are sequential;
comparisons are done afterwards by compare2.py so they do not overlap the timed runs.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOB = HERE.parent
PY = r'<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
B00 = Path(r'<jobs>\20261103_gral_gpu_final_validation\runs\final448_001\targets\B00_fixed00_cpu')


def main():
    label, build, specs = sys.argv[1], sys.argv[2], sys.argv[3:]
    for spec in specs:
        case, variant = spec.split(':')
        run = f'{label}_{case}_{variant}'
        env = dict(os.environ, SMOKE_REF_DIR=str(B00 if case == 'B00' else HERE / 'cases' / case),
                   SMOKE_INU_GPU_CACHE_DIR=str(JOB / 'cache_sweep'))
        if variant not in ('cpu', 'D'):
            env['SMOKE_RUNTIME'] = str(HERE / f'rt_{variant}')
        mode = 'cpu' if variant == 'cpu' else 'gpu'
        out = subprocess.run([PY, '-X', 'utf8', '-B', str(JOB / 'smoke_pinvoke.py'), mode, run, build],
                             env=env, capture_output=True, text=True)
        res = json.loads(out.stdout.strip().splitlines()[-1])
        row = {'run': run, 'case': case, 'variant': variant, 'rc': res['rc'], 'wall_s': res['wall_s'],
               'fallback': res['gpu_fallback_lines']}
        if mode == 'gpu':
            metrics = [json.loads(l) for l in open(JOB / 'smoke' / run / 'logs' / 'gpu_metrics.jsonl')]
            last = metrics[-1]['result_server_metrics']
            row.update(kernel_device_s=round(last['kernel_device_ms'] / 1000, 3), launches=last['kernel_launches'],
                       fresh_regs=metrics[0]['init_server']['metrics_cumulative']['kernel_resources']['fresh'].get('registers'))
        with (HERE / f'runs2_{label}.jsonl').open('a', encoding='utf8') as f:
            f.write(json.dumps(row) + '\n')
        print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
