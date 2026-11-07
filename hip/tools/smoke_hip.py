"""B00-family smoke of the HIP-port build on the RX 9070 XT against the frozen CUDA-study outputs.

Usage: smoke_hip.py <cpu|gpu> <label> <build folder> [reference name, default B00_fixed00]
Copies the frozen fixed-seed inputs of <reference>_<mode> from the final-validation study, runs all situations
on CPUs 0-15 (Job Object), then compares GRZ members with compare.py against
  - the frozen CPU output (<reference>_cpu),
  - the frozen CUDA GPU output (<reference>_gpu, RTX 5080, study build),
and writes smoke_result.json plus the two full comparison JSONs. Not timing-eligible while 7-Zip runs.
"""
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

FV = Path(r'<jobs>\20261103_gral_gpu_final_validation')
sys.path.insert(0, str(FV / 'validation'))
from support.runtime_helpers import run_contained  # noqa: E402
import compare  # noqa: E402

JOB = Path(__file__).resolve().parent
RUNTIME = Path(os.environ['SMOKE_RUNTIME']) if os.environ.get('SMOKE_RUNTIME') else JOB / 'repo' / 'gpu' / 'runtime'
HIPRTC = Path(os.environ.get('SMOKE_HIPRTC_DIR', r'<user>\AppData\Local\rocm-sdk\venv-10.1\Lib\site-packages\_rocm_sdk_core\bin'))
MASK = 0x0000FFFF


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def members(folder):
    out = {}
    for grz in sorted(folder.glob('*.grz')):
        with zipfile.ZipFile(grz) as z:
            for n in z.namelist():
                out[grz.name + '/' + n] = hashlib.sha256(z.read(n)).hexdigest()
    return out


def summary(cmp):
    con = [r for r in cmp['per_hour'] if r['extension'] == 'con']
    tot_ref = sum(r['reference_sum'] for r in con)
    tot_abs = sum(r['nmae'] * r['reference_sum'] for r in con if r['nmae'] is not None)
    return {'raw_members_equal': cmp['raw_members_equal'],
            'members_identical': sum(1 for m in cmp['members'] if m['raw_equal']), 'members': len(cmp['members']),
            'con_nmae_pooled': tot_abs / tot_ref if tot_ref else None,
            'con_nmae_max_hour': max((r['nmae'] for r in con if r['nmae'] is not None), default=None),
            'con_bias_pooled': (sum(r['candidate_sum'] for r in con) - tot_ref) / tot_ref if tot_ref else None,
            'con_jaccard_min_hour': min((r['positive_support_jaccard'] for r in con), default=None),
            'receptors_equal': [r['raw_equal'] for r in cmp['receptors']]}


def main():
    mode, label, build = sys.argv[1], sys.argv[2], (JOB / sys.argv[3]).resolve()
    refname = sys.argv[4] if len(sys.argv) > 4 else 'B00_fixed00'
    dll = build / 'out' / 'GRAL.dll'
    src = FV / f'runs/final448_001/targets/{refname}_{mode}'
    manifest = json.loads((src / 'input_manifest.json').read_text(encoding='utf8'))
    target = JOB / 'smoke' / label
    target.mkdir(parents=True)
    for name, digest in manifest['input_sha256'].items():
        d = target / name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / name, d)
        if sha(d) != digest:
            raise ValueError('input hash mismatch ' + name)
    logs = target / 'logs'
    logs.mkdir()
    temp = target / 'temp'
    temp.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('INU_', 'GRAL_', 'DOTNET_Tiered'))}
    env.update(TEMP=str(temp), TMP=str(temp), INU_GPU_EXPERIMENTAL='1' if mode == 'gpu' else '0',
               GRAL_BENCH_SEED_OFFSET=str(manifest['seed_control']['offset']))
    if mode == 'gpu':
        env.update(INU_GPU_MANIFEST=str(RUNTIME / 'fields_manifest.json'), INU_GPU_METRICS=str(logs / 'gpu_metrics.jsonl'),
                   INU_GPU_STDERR=str(logs / 'gpu_server.stderr'), INU_GPU_HIPRTC_DIR=str(HIPRTC))
        backend = os.environ.get('SMOKE_BACKEND', 'hip')  # 'auto' leaves INU_GPU_BACKEND unset
        if backend != 'auto':
            env['INU_GPU_BACKEND'] = backend
        if os.environ.get('SMOKE_FALLBACK'):
            env['INU_GPU_FALLBACK_ON_STARTUP'] = os.environ['SMOKE_FALLBACK']
        for key in ('INU_GPU_DEVICE', 'INU_GPU_CACHE_DIR', 'INU_GPU_MEMORY_BUDGET_BYTES', 'INU_GRAL_GPU_BLOCK', 'INU_GRAL_GPU_CHUNK',
                    'INU_GPU_MAX_KERNEL_MS', 'INU_GPU_HIP_RUNTIME', 'INU_GPU_HIPRTC_EXTRA'):
            if os.environ.get('SMOKE_' + key):
                env[key] = os.environ['SMOKE_' + key]
    cmd = ['dotnet', str(dll), str(target / 'Computation'), f'SITUATIONS:1:{manifest["hours"]}']
    rec = []
    t0 = time.perf_counter()
    with (logs / 'stdout.log').open('xb') as so, (logs / 'stderr.log').open('xb') as se:
        pid, rc, timed_out = run_contained(cmd, target / 'Computation', env, so, se, int(os.environ.get('SMOKE_TIMEOUT', '3600')),
                                           expected_affinity_mask=MASK, affinity_record=rec)
    wall = time.perf_counter() - t0
    stdout = (logs / 'stdout.log').read_bytes().decode('utf8', 'replace')
    res = {'mode': mode, 'reference_case': refname, 'dll_sha256': sha(dll), 'rc': rc, 'timed_out': timed_out, 'wall_s': round(wall, 3),
           'gpu_fallback_lines': [l[:700] for l in stdout.splitlines() if 'GPU fallback' in l or 'GPU startup' in l],
           'gpu_device_line': [l for l in stdout.splitlines() if l.startswith('GPU device')][:1],
           'gpu_metrics_lines': sum(1 for _ in open(logs / 'gpu_metrics.jsonl')) if (logs / 'gpu_metrics.jsonl').exists() else None,
           'timing_eligible': False}
    if rc == 0:
        groups = tuple(manifest.get('source_groups', (1, 2, 3)))
        cfg = manifest['config']
        for refmode in ('cpu', 'gpu'):
            ref = FV / f'runs/final448_001/targets/{refname}_{refmode}' / 'Computation'
            cmp = compare.compare_outputs(ref, target / 'Computation', hours=manifest['hours'], expected_groups=groups,
                                          deposition=cfg.get('deposition', False),
                                          required_receptors=('Receptor_Timeseries_Transient.txt',) if cfg.get('receptors') else (),
                                          expected_receptor_columns=cfg['receptors'] * len(groups) if cfg.get('receptors') else None)
            (target / f'compare_vs_frozen_{refmode}.json').write_text(json.dumps(cmp, indent=1, allow_nan=False), encoding='utf8')
            res['vs_frozen_' + refmode] = summary(cmp)
    (target / 'smoke_result.json').write_text(json.dumps(res, indent=1), encoding='utf8')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
