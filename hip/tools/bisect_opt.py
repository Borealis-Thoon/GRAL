"""Find the LLVM optimization step that breaks the HIP -O2 kernel, with -mllvm -opt-bisect-limit.

Runs B00_fixed00 situation 1 only and compares 00001.grz with the frozen CUDA output (NMAE over all .con members).
-O1 gives NMAE ~0.004 and -O2 ~1.36 in situation 1, so the split between good and bad is unambiguous.
Usage: bisect_opt.py count | bisect_opt.py run <limit> | bisect_opt.py search <lo_good> <hi_bad>
"""
import json, os, re, shutil, subprocess, sys, time, zipfile
from pathlib import Path

FV = Path(r'<jobs>\20261103_gral_gpu_final_validation')
sys.path.insert(0, str(FV / 'validation'))
import compare  # noqa: E402

JOB = Path(__file__).resolve().parent
SRC = FV / 'runs/final448_001/targets/B00_fixed00_gpu'
REF = SRC / 'Computation' / '00001.grz'
DLL = JOB / 'build_hip2' / 'out' / 'GRAL.dll'
RUNTIME = JOB / 'repo' / 'gpu' / 'runtime'
HIPRTC = r'<user>\AppData\Local\rocm-sdk\venv-10.1\Lib\site-packages\_rocm_sdk_core\bin'
WORK = JOB / 'bisect'
CACHE = WORK / 'module_cache'


def nmae_hour1(cand_grz):
    tot_abs = tot_ref = 0.0
    with zipfile.ZipFile(REF) as za, zipfile.ZipFile(cand_grz) as zb:
        for name in za.namelist():
            if not name.endswith('.con'):
                continue
            a, b = compare.read_grid(za.read(name)), compare.read_grid(zb.read(name))
            av, bv = compare.align(a, b)
            tot_abs += sum(abs(x - y) for x, y in zip(av, bv)); tot_ref += sum(av)
    return tot_abs / tot_ref


def run(extra, label):
    target = WORK / label
    if target.exists():
        shutil.rmtree(target)
    man = json.loads((SRC / 'input_manifest.json').read_text(encoding='utf8'))
    for name in man['input_sha256']:
        d = target / name; d.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(SRC / name, d)
    (target / 'temp').mkdir(); (target / 'logs').mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('INU_', 'GRAL_'))}
    env.update(TEMP=str(target / 'temp'), TMP=str(target / 'temp'), INU_GPU_EXPERIMENTAL='1', INU_GPU_BACKEND='hip',
               INU_GPU_HIPRTC_DIR=HIPRTC, INU_GPU_MANIFEST=str(RUNTIME / 'fields_manifest.json'),
               INU_GPU_METRICS=str(target / 'logs' / 'gpu_metrics.jsonl'), INU_GPU_STDERR=str(target / 'logs' / 'gpu_server.stderr'),
               INU_GPU_HIPRTC_EXTRA=extra, INU_GPU_CACHE_DIR=str(CACHE),
               GRAL_BENCH_SEED_OFFSET=str(man['seed_control']['offset']))
    t0 = time.time()
    with open(target / 'logs' / 'stdout.log', 'wb') as so, open(target / 'logs' / 'stderr.log', 'wb') as se:
        rc = subprocess.run(['dotnet', str(DLL), str(target / 'Computation'), 'SITUATIONS:1:1'], cwd=target / 'Computation',
                            env=env, stdout=so, stderr=se, timeout=1800).returncode
    out = target / 'Computation' / '00001.grz'
    fallback = [l for l in (target / 'logs' / 'stdout.log').read_text(errors='replace').splitlines() if 'GPU fallback' in l or 'GPU startup' in l]
    val = nmae_hour1(out) if rc == 0 and out.exists() and not fallback else None
    return rc, val, round(time.time() - t0, 1), target


def bisect_lines(target):
    text = (target / 'logs' / 'stderr.log').read_text(errors='replace') + (target / 'logs' / 'gpu_server.stderr').read_text(errors='replace') \
        if (target / 'logs' / 'gpu_server.stderr').exists() else (target / 'logs' / 'stderr.log').read_text(errors='replace')
    return [l for l in text.splitlines() if l.startswith('BISECT:')]


def main():
    WORK.mkdir(exist_ok=True)
    cmd = sys.argv[1]
    if cmd == 'count':
        rc, val, wall, target = run('-O2 -mllvm -opt-bisect-limit=100000000', 'count')
        lines = bisect_lines(target)
        print('rc', rc, 'nmae', val, 'wall', wall, 'bisect lines', len(lines))
        print('\n'.join(lines[-3:]))
    elif cmd == 'run':
        n = int(sys.argv[2])
        rc, val, wall, target = run(f'-O2 -mllvm -opt-bisect-limit={n}', f'n{n}')
        print(json.dumps({'limit': n, 'rc': rc, 'nmae': val, 'wall': wall}))
    elif cmd == 'search':
        lo, hi = int(sys.argv[2]), int(sys.argv[3])  # lo good, hi bad
        log = []
        while hi - lo > 1:
            mid = (lo + hi) // 2
            rc, val, wall, target = run(f'-O2 -mllvm -opt-bisect-limit={mid}', f'n{mid}')
            good = val is not None and val < 0.05
            log.append({'limit': mid, 'rc': rc, 'nmae': val, 'wall': wall, 'good': good})
            print(json.dumps(log[-1]), flush=True)
            if val is None:
                break
            if good: lo = mid
            else: hi = mid
            shutil.rmtree(target / 'Computation', ignore_errors=True)
        rc, val, wall, target = run(f'-O2 -mllvm -opt-bisect-limit={hi}', f'n{hi}_final')
        lines = bisect_lines(target)
        culprit = [l for l in lines if re.search(rf'\({hi}\)', l)]
        res = {'last_good': lo, 'first_bad': hi, 'culprit_lines': culprit[:5], 'steps': log}
        (WORK / 'bisect_result.json').write_text(json.dumps(res, indent=1), encoding='utf8')
        print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
