"""Repeat fixed-seed GRAL runs (CPU and CUDA GPU; copy of the HIP harness of 20261111_gral_gpu_reproducible_sums) of the PR #77 head build and record output identity.

Usage: repeat_runs.py <plan json> <out dir>
plan: {"dll": ..., "runtime": ..., "hiprtc": ..., "runs": [{"case": "<suite case>|frozen:<B00_fixed00>",
        "label": "gpu_r1", "mode": "gpu"|"cpu", "env": {...}}]}
Suite cases are materialized with the feature-suite fixtures (fixtures_ext.prepare); frozen cases copy the
inputs of the final448 study targets. Every run is pinned to logical CPUs 0-15 (Job Object) and runs serially.
Not timing-eligible.
"""
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

SUITE = Path(r'D:\INU_Modeling_Work\jobs\20261104_gral_gpu_feature_suite')
FV = Path(r'D:\INU_Modeling_Work\jobs\20261103_gral_gpu_final_validation')
sys.path.insert(0, str(SUITE))
sys.path.insert(1, str(FV / 'validation'))
import fixtures_ext as fx  # noqa: E402
import suite_io as sio  # noqa: E402
from support.runtime_helpers import run_contained  # noqa: E402

MASK = 0x0000FFFF
OUTPUT_SKIP_PREFIX = ('Logfile_', )


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def template(out, case):
    if case.startswith('frozen:'):
        name = case.split(':', 1)[1]
        src = FV / f'runs/final448_001/targets/{name}_gpu'
        t = out / 'templates' / name
        if not (t / 'input_manifest.json').exists():
            man = json.loads((src / 'input_manifest.json').read_text(encoding='utf8'))
            for rel, digest in man['input_sha256'].items():
                d = t / rel
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src / rel, d)
                if sha(d) != digest:
                    raise ValueError('input hash mismatch ' + rel)
            (t / 'input_manifest.json').write_text(json.dumps(man), encoding='utf8')
        return t, json.loads((t / 'input_manifest.json').read_text(encoding='utf8'))['hours'], 3600
    t = out / 'templates' / case
    if not (t / 'input_manifest.json').exists():
        if t.exists():
            shutil.rmtree(t)
        fx.prepare(t, case)
    return t, fx.HOURS, fx.CASES[case]['timeout'] if case in fx.CASES else 1800


def output_hashes(comp, inputs):
    res = {}
    for p in sorted(comp.iterdir()):
        if p.is_dir() or p.name in inputs or p.name.startswith(OUTPUT_SKIP_PREFIX):
            continue
        if p.suffix == '.grz':
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    res[p.name + '/' + n] = hashlib.sha256(z.read(n)).hexdigest()
        else:
            res[p.name] = sha(p)
    return res


def main():
    plan = json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    nvrtc = Path(plan['nvrtc'])
    for r in plan['runs']:
        dll = Path(r.get('dll', plan['dll']))
        runtime = Path(r.get('runtime', plan['runtime']))
        t, hours, timeout = template(out, r['case'])
        key = r['case'].replace(':', '_')
        dest = out / key / r['label']
        if (dest / 'run_info.json').exists():
            continue
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(t, dest)
        comp = dest / 'Computation'
        inputs = {p.name for p in (t / 'Computation').iterdir()}
        logs, temp = dest / 'logs', dest / 'temp'
        logs.mkdir(exist_ok=True); temp.mkdir(exist_ok=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith(('INU_', 'GRAL_', 'DOTNET_Tiered'))}
        env.update(TEMP=str(temp), TMP=str(temp), INU_GPU_EXPERIMENTAL='1' if r['mode'] == 'gpu' else '0')
        if r['mode'] == 'gpu':
            env.update(INU_GPU_MANIFEST=str(runtime / 'fields_manifest.json'), INU_GPU_METRICS=str(logs / 'gpu_metrics.jsonl'),
                       INU_GPU_STDERR=str(logs / 'gpu_runtime.log'), INU_GPU_NVRTC_DIR=str(nvrtc), INU_GPU_BACKEND='cuda')
        for k, v in r.get('env', {}).items():
            if v is None:
                env.pop(k, None)   # null in the plan removes a default setting
            else:
                env[k] = v
        cmd = ['dotnet', str(dll), str(comp)]
        if not (comp / 'GRAL_Vert_Conc.txt').exists():
            cmd.append(f'SITUATIONS:1:{hours}')
        t0 = time.perf_counter()
        with (logs / 'stdout.log').open('xb') as so, (logs / 'stderr.log').open('xb') as se:
            _, rc, timed_out = run_contained(cmd, comp, env, so, se, timeout * 3, expected_affinity_mask=MASK, affinity_record=[])
        stdout = (logs / 'stdout.log').read_bytes().decode('utf8', 'replace')
        info = {'case': r['case'], 'label': r['label'], 'mode': r['mode'], 'env': r.get('env', {}), 'rc': rc, 'timed_out': timed_out,
                'wall_s': round(time.perf_counter() - t0, 2), 'dll_sha256': sha(dll),
                'fallback_lines': [l[:400] for l in stdout.splitlines() if 'GPU fallback' in l or 'GPU startup' in l],
                'device_line': [l for l in stdout.splitlines() if l.startswith('GPU device')][:1],
                'gpu_lines': [l[:300] for l in stdout.splitlines() if l.startswith('GPU ')][:8],
                'deterministic_mode_line': 'GRAL Deterministic Mode' in stdout,
                'gpu_metrics_lines': sio.count_metrics_lines(logs / 'gpu_metrics.jsonl') if r['mode'] == 'gpu' else None,
                'outputs': output_hashes(comp, inputs)}
        (dest / 'run_info.json').write_text(json.dumps(info, indent=1), encoding='utf8')
        print(f"[RUN] {key} {r['label']} rc={rc} wall={info['wall_s']}s outputs={len(info['outputs'])} det={info['deterministic_mode_line']} fb={len(info['fallback_lines'])}", flush=True)


if __name__ == '__main__':
    main()
