"""Full-precision EmissionPerSG check: run B00 (all 25 situations, no SITUATIONS argument) with
KeepAndReadTransientTempFiles.dat so GRAL keeps Transient_Concentrations*.tmp written at situation 24, then read the
per-source-group EmissionPerSG doubles that WriteTransientConcentration appends after the concentration block.

Usage: run_ckpt.py <cpu|gpu> <label> <build folder> [runtime folder]
Writes perf2/ckpt/<label>/ckpt_result.json with EmissionPerSG (repr of each double) and the tmp file SHA256.
"""
import hashlib
import io
import json
import os
import shutil
import struct
import sys
import time
import zipfile
from pathlib import Path

FV = Path(r'<jobs>\20261103_gral_gpu_final_validation')
sys.path.insert(0, str(FV / 'validation'))
from support.runtime_helpers import run_contained  # noqa: E402

P2 = Path(__file__).resolve().parent
JOB = P2.parent
HIPRTC = Path(r'<user>\AppData\Local\rocm-sdk\venv-10.1\Lib\site-packages\_rocm_sdk_core\bin')


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def emission_per_sg(tmp):
    with zipfile.ZipFile(tmp) as z:
        data = z.read(z.namelist()[0])
    r = io.BytesIO(data)
    nii, njj, nkk = struct.unpack('<iii', r.read(12))
    r.read(4 * 8 + 4)  # GralWest..GralNorth (double) + DXK (float)
    iwet, nsg = struct.unpack('<ii', r.read(8))
    # concentration block: (NJJ+1)*(NII+1)*NSG*(NKK+1) floats, as written by WriteTransientConcentration
    body = len(data) - r.tell()
    tail = 8 * nsg
    vals = struct.unpack('<%dd' % nsg, data[-tail:])
    return {'nii': nii, 'njj': njj, 'nkk': nkk, 'iwet': iwet, 'nsg': nsg, 'payload_bytes': body,
            'emission_per_sg': [repr(v) for v in vals], 'emission_per_sg_hex': [struct.pack('<d', v).hex() for v in vals]}


def main():
    mode, label, build = sys.argv[1], sys.argv[2], (JOB / sys.argv[3]).resolve()
    runtime = Path(sys.argv[4]) if len(sys.argv) > 4 else JOB / 'pr77_hip' / 'gpu' / 'runtime'
    src = FV / 'runs/final448_001/targets/B00_fixed00_gpu'
    manifest = json.loads((src / 'input_manifest.json').read_text(encoding='utf8'))
    target = P2 / 'ckpt' / label
    target.mkdir(parents=True)
    for name in manifest['input_sha256']:
        d = target / name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / name, d)
    comp = target / 'Computation'
    (comp / 'KeepAndReadTransientTempFiles.dat').write_text('24\r\n', encoding='ascii')
    logs = target / 'logs'
    logs.mkdir()
    temp = target / 'temp'
    temp.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('INU_', 'GRAL_', 'DOTNET_Tiered'))}
    env.update(TEMP=str(temp), TMP=str(temp), INU_GPU_EXPERIMENTAL='1' if mode == 'gpu' else '0',
               GRAL_BENCH_SEED_OFFSET=str(manifest['seed_control']['offset']))
    if mode == 'gpu':
        env.update(INU_GPU_MANIFEST=str(runtime / 'fields_manifest.json'), INU_GPU_METRICS=str(logs / 'gpu_metrics.jsonl'),
                   INU_GPU_STDERR=str(logs / 'gpu_server.stderr'), INU_GPU_HIPRTC_DIR=str(HIPRTC), INU_GPU_BACKEND='hip')
    cmd = ['dotnet', str(build / 'out' / 'GRAL.dll'), str(comp)]
    t0 = time.perf_counter()
    with (logs / 'stdout.log').open('xb') as so, (logs / 'stderr.log').open('xb') as se:
        pid, rc, timed_out = run_contained(cmd, comp, env, so, se, 1800, expected_affinity_mask=0x0000FFFF, affinity_record=[])
    res = {'mode': mode, 'label': label, 'build': str(build), 'dll_sha256': sha(build / 'out' / 'GRAL.dll'), 'rc': rc,
           'wall_s': round(time.perf_counter() - t0, 2)}
    tmps = sorted(comp.glob('Transient_Concentrations*.tmp'))
    res['tmp_files'] = {p.name: sha(p) for p in tmps}
    if tmps:
        newest = max(tmps, key=lambda p: p.stat().st_mtime)
        res['checkpoint'] = newest.name
        res.update(emission_per_sg(newest))
    (target / 'ckpt_result.json').write_text(json.dumps(res, indent=1), encoding='utf8')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
