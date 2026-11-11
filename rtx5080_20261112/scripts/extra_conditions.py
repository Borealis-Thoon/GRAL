"""Extra GRAL run conditions on the Radeon that the feature suite does not cover.

Reuses the suite's templates and run_arm. Fixed-seed GPU outputs are compared byte by byte
(decompressed .grz members and text outputs) with the suite's gpu_fixed run of the same case.
"""
import argparse
import json
import sys
import threading
import zipfile
from pathlib import Path
from types import SimpleNamespace

SUITE_CODE = Path(r'D:\INU_Modeling_Work\jobs\20261104_gral_gpu_feature_suite')
sys.path.insert(0, str(SUITE_CODE))
import run_suite as rs  # noqa: E402

DLL = Path(r'D:\INU_Modeling_Work\jobs\20261111_gral_gpu_reproducible_sums\builds\head_6d22298\out\GRAL.dll')
RUNTIME = Path(r'D:\INU_Modeling_Work\jobs\20261111_gral_gpu_radeon_stability\runtime')
SUITE_OUT = Path(r'D:\INU_Modeling_Work\jobs\20261111_gral_gpu_radeon_stability\suite')
TEXT_OUTPUTS = ('ReceptorConcentrations.dat', 'Receptor_Timeseries_Transient.txt', 'Vertical_Concentrations.txt')


def outputs(comp: Path) -> dict:
    """Map of output member name -> bytes, ignoring zip timestamps."""
    res = {}
    for g in sorted(comp.glob('*.grz')):
        with zipfile.ZipFile(g) as z:
            for n in z.namelist():
                res[g.name + '/' + n] = z.read(n)
    for name in TEXT_OUTPUTS:
        p = comp / name
        if p.exists():
            res[name] = p.read_bytes()
    for p in sorted(comp.glob('*.odr')) + sorted(comp.glob('*.dep')):
        res[p.name] = p.read_bytes()
    return res


def compare(a: Path, b: Path) -> dict:
    oa, ob = outputs(a), outputs(b)
    diff = sorted(k for k in oa.keys() | ob.keys() if oa.get(k) != ob.get(k))
    return {'members_a': len(oa), 'members_b': len(ob), 'differing': len(diff), 'first_differing': diff[:5]}


def set_in_dat_line(comp: Path, index: int, value: str) -> None:
    lines = (comp / 'in.dat').read_text(encoding='ascii').splitlines()
    tail = lines[index].split('!', 1)
    lines[index] = value + ' \t!' + tail[1] if len(tail) == 2 else value
    (comp / 'in.dat').write_text('\n'.join(lines) + '\n', encoding='ascii', newline='\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--only', default='')
    ap.add_argument('--dll', type=Path, default=None)
    ap.add_argument('--runtime', type=Path, default=None)
    ap.add_argument('--suite', type=Path, default=None, help='feature-suite output to compare with (default: the Radeon suite)')
    args = ap.parse_args()
    global DLL, RUNTIME, SUITE_OUT
    if args.suite:
        SUITE_OUT = args.suite.resolve()
    if args.dll:
        DLL = args.dll.resolve()
    if args.runtime:
        RUNTIME = args.runtime.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    suite = rs.Suite(SimpleNamespace(dll=DLL, runtime=RUNTIME, out=SUITE_OUT, allow_unvalidated=True, gpu_native=True))
    H = rs.fx.HOURS
    results = {}

    def run(name, case, extra, situations=H, in_dat=None, dest=None):
        t = suite.template(case)
        d = dest or (out / name)
        if in_dat and not (d / 'run_info.json').exists():
            # copy template, patch in.dat, then run from the patched copy
            import shutil
            pt = out / ('_tpl_' + name)
            if pt.exists():
                shutil.rmtree(pt)
            shutil.copytree(t, pt)
            for idx, val in in_dat.items():
                set_in_dat_line(pt / 'Computation', idx, val)
            t = pt
        info = suite.run_arm(t, d, 'gpu', False, situations, 1800, extra)
        return info, d / 'Computation'

    def record(name, info, comp, ref_case=None, expect_identical=True):
        r = {k: info.get(k) for k in ('rc', 'timed_out', 'wall_s', 'fallback_lines', 'gpu_situations', 'server_startup', 'extra_env')}
        if ref_case:
            r['vs_suite_gpu_fixed'] = compare(comp, SUITE_OUT / ref_case / 'gpu_fixed' / 'Computation')
            r['expect_identical'] = expect_identical
        results[name] = r
        print(name, json.dumps(r, ensure_ascii=False)[:600], flush=True)

    todo = [s for s in args.only.split(',') if s]

    def want(n):
        return not todo or n in todo

    # E1: two GRAL processes on one GPU at the same time (fixed seed, reproducible sums)
    if want('concurrent'):
        box = {}

        def worker(tag):
            box[tag] = run('concurrent_' + tag, 'transient_area', {})
        ts = [threading.Thread(target=worker, args=(t,)) for t in ('a', 'b')]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        for tag in ('a', 'b'):
            record('concurrent_' + tag, *box[tag], ref_case='transient_area')
        results['concurrent_a_vs_b'] = compare(box['a'][1], box['b'][1])
    # E2: general (not specialized) kernel
    if want('specialize0'):
        record('specialize0', *run('specialize0', 'transient_all_sources', {'INU_GPU_SPECIALIZE': '0'}), ref_case='transient_all_sources')
    # E3: reproducible sums switched off (fixed seed): must run, need not be identical
    if want('repro_off'):
        record('repro_off', *run('repro_off', 'transient_area', {'INU_GPU_REPRODUCIBLE_SUMS': '0'}), ref_case='transient_area', expect_identical=False)
    # E4: tiny device budget -> outputs and sum words in mapped host memory
    if want('budget_tiny'):
        record('budget_tiny', *run('budget_tiny', 'transient_all_sources', {'INU_GPU_MEMORY_BUDGET_BYTES': '131072'}), ref_case='transient_all_sources')
    if want('budget_tiny_steady'):
        record('budget_tiny_steady', *run('budget_tiny_steady', 'steady_rot_all_sources', {'INU_GPU_MEMORY_BUDGET_BYTES': '131072'}), ref_case='steady_rot_all_sources')
    # E5: launch shape (block 256, small chunk) with reproducible sums
    if want('block256_chunk4096'):
        record('block256_chunk4096', *run('block256_chunk4096', 'transient_all_sources', {'INU_GRAL_GPU_BLOCK': '256', 'INU_GRAL_GPU_CHUNK': '4096'}), ref_case='transient_all_sources')
    # E6: situation range starting in the middle (GUI multi-instance style)
    if want('range_7_12'):
        t = suite.template('transient_area')
        d = out / 'range_7_12'
        if not (d / 'run_info.json').exists():
            import shutil
            import time
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(t, d)
            comp = d / 'Computation'
            logs, temp = d / 'logs', d / 'temp'
            logs.mkdir(); temp.mkdir()
            env = suite.env('gpu', logs, temp, {})
            t0 = time.perf_counter()
            with (logs / 'stdout.log').open('xb') as so, (logs / 'stderr.log').open('xb') as se:
                _, rc, to = rs.run_contained(['dotnet', str(DLL), str(comp), 'SITUATIONS:7:12'], comp, env, so, se, 1800,
                                             expected_affinity_mask=rs.MASK, affinity_record=[])
            info = {'rc': rc, 'timed_out': to, 'wall_s': round(time.perf_counter() - t0, 2),
                    'fallback_lines': rs.sio.fallback_lines((logs / 'stdout.log').read_bytes().decode('utf8', 'replace')),
                    'gpu_situations': rs.sio.count_metrics_lines(logs / 'gpu_metrics.jsonl')}
            (d / 'run_info.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
        info = json.loads((d / 'run_info.json').read_text(encoding='utf-8'))
        grz = sorted(p.name for p in (d / 'Computation').glob('*.grz'))
        info['grz'] = grz
        results['range_7_12'] = info
        print('range_7_12', json.dumps(info)[:600], flush=True)
    # E8: zero configuration: only INU_GPU_EXPERIMENTAL=1 (manifest next to GRAL, logs in Computation by default)
    for case in ('transient_area', 'transient_all_sources', 'steady_rot_all_sources'):
        name = 'zero_config_' + case
        if not want(name):
            continue
        import shutil
        import time
        t = suite.template(case)
        d = out / name
        if not (d / 'run_info.json').exists():
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(t, d)
            comp = d / 'Computation'
            logs, temp = d / 'logs', d / 'temp'
            logs.mkdir(); temp.mkdir()
            env = {k: v for k, v in rs.os.environ.items() if not k.startswith(('INU_', 'GRAL_'))}
            env.update(TEMP=str(temp), TMP=str(temp), INU_GPU_EXPERIMENTAL='1', INU_GPU_ALLOW_UNVALIDATED='1')
            t0 = time.perf_counter()
            with (logs / 'stdout.log').open('xb') as so, (logs / 'stderr.log').open('xb') as se:
                _, rc, to = rs.run_contained(['dotnet', str(DLL), str(comp), f'SITUATIONS:1:{H}'], comp, env, so, se, 1800,
                                             expected_affinity_mask=rs.MASK, affinity_record=[])
            info = {'rc': rc, 'timed_out': to, 'wall_s': round(time.perf_counter() - t0, 2),
                    'fallback_lines': rs.sio.fallback_lines((logs / 'stdout.log').read_bytes().decode('utf8', 'replace')),
                    'gpu_situations': rs.sio.count_metrics_lines(comp / 'GRAL_GPU_metrics.jsonl'),
                    'default_logs': sorted(p.name for p in comp.glob('GRAL_GPU_*'))}
            (d / 'run_info.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
        info = json.loads((d / 'run_info.json').read_text(encoding='utf-8'))
        record(name, info, d / 'Computation', ref_case=case)
    # E7: AVX-512 option on together with the GPU
    if want('avx512_on'):
        record('avx512_on', *run('avx512_on', 'transient_area', {}, in_dat={20: '1'}), ref_case='transient_area')

    (out / 'extra_results.json').write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
