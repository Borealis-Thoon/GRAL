"""Output comparisons for the runs2.py label: every variant against the CPU and the double GPU run of the same case.

Usage: compare2.py <label>
Pairs (ref, test):
  B00   variants vs frozen B00_fixed00_cpu and vs <label>_B00_D
  B00s  variants vs <label>_B00s_cpu and vs <label>_B00s_D
  noise B00s_native_cpu vs B00s_cpu (seed noise of the shifted case)
  shift B00s_cpu vs frozen B00 CPU, B00s_D vs <label>_B00_D (record coordinates moved back by the shift)
Writes precision/compare2_<label>.json.
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE.parent / 'smoke'
PYM = r'<work>\envs\modeling-tools\Scripts\python.exe'
B00_CPU = Path(r'<jobs>\20261103_gral_gpu_final_validation\runs\final448_001\targets\B00_fixed00_cpu\Computation')
VARIANTS = ('D2', 'M', 'F', 'M2', 'F2')
SHIFT = ('150000', '430000')


def comp(label):
    return lambda run: SMOKE / f'{label}_{run}' / 'Computation'


def compare(ref, test, shift=()):
    out = subprocess.run([PYM, '-X', 'utf8', '-B', str(HERE / 'compare_grz.py'), str(ref), str(test), *shift],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    label = sys.argv[1]
    c = comp(label)
    pairs = {'B00:D vs cpu': (B00_CPU, c('B00_D'), ())}
    for v in VARIANTS:
        pairs[f'B00:{v} vs cpu'] = (B00_CPU, c(f'B00_{v}'), ())
        pairs[f'B00:{v} vs D'] = (c('B00_D'), c(f'B00_{v}'), ())
        pairs[f'B00s:{v} vs cpu'] = (c('B00s_cpu'), c(f'B00s_{v}'), ())
        pairs[f'B00s:{v} vs D'] = (c('B00s_D'), c(f'B00s_{v}'), ())
    pairs['B00s:D vs cpu'] = (c('B00s_cpu'), c('B00s_D'), ())
    pairs['B00s noise: native cpu vs cpu'] = (c('B00s_cpu'), c('B00s_native_cpu'), ())
    pairs['shift: B00s cpu vs B00 cpu'] = (B00_CPU, c('B00s_cpu'), SHIFT)
    pairs['shift: B00s D vs B00 D'] = (c('B00_D'), c('B00s_D'), SHIFT)
    with ThreadPoolExecutor(8) as pool:
        futures = {k: pool.submit(compare, *v) for k, v in pairs.items()}
        result = {k: f.result() for k, f in futures.items()}
    (HERE / f'compare2_{label}.json').write_text(json.dumps(result, indent=1), encoding='utf8')
    for k, v in result.items():
        print(f"{k:34s} rel={v['relative']:.5f} max={v['max_abs_diff']:.3f} identical={v['identical_members']}/{v['members']} "
              f"top1%={v['top1pct_rel_diff']:+.2e} sum={v['sum_rel_diff']:+.2e}")


if __name__ == '__main__':
    main()
