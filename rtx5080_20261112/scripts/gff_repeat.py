"""Repeatability of a GUI project with GRAMM terrain, prognostic buildings and a precomputed *.gff flow field (the setup of
the maintainer's GTX 1650 report) on the RTX 5080. Fixed seeds ("reproducible results" = 1 in in.dat). Two GPU runs with the
default integer sums and two with INU_GPU_REPRODUCIBLE_SUMS=0. Only INU_GPU_EXPERIMENTAL=1 is set otherwise (zero config,
NVRTC from INU_GPU_NVRTC_DIR because CUDA_PATH is not set on this PC).
Usage: gff_repeat.py <out dir>
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

SRC = Path(r'D:\INU_Modeling_Work\jobs\20261111_gral_gui_gpu_button\testproject2\Computation')
DLL = Path(r'D:\INU_Modeling_Work\jobs\20261111_gral_gpu_reproducible_sums\builds\head_63ce3c6\out\GRAL.dll')
NVRTC = r'D:\INU_Modeling_Work\jobs\20261031_132339_gral_gramm_gpu_resident\work\gral_host\candidate_gpu\support\nvrtc\nvidia\cuda_nvrtc\bin'
OUTPUT = ('.grz', '.txt', '.dat')
RUNS = [('on1', {}), ('on2', {}), ('off1', {'INU_GPU_REPRODUCIBLE_SUMS': '0'}), ('off2', {'INU_GPU_REPRODUCIBLE_SUMS': '0'})]


def members(comp, inputs):
    res = {}
    for p in sorted(comp.iterdir()):
        if p.is_dir() or p.name in inputs or p.name.startswith(('Logfile_', 'GRAL_GPU_', 'Percent', 'DispNr')):
            continue
        if p.suffix == '.grz':
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    res[p.name + '/' + n] = hashlib.sha256(z.read(n)).hexdigest()
        elif p.suffix in OUTPUT:
            res[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return res


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    keep = {p.name for p in SRC.iterdir() if p.suffix != '.grz' and not p.name.startswith(('Logfile_GRAL', 'GRAL_GPU_'))
            and not p.name.endswith(('-101.txt',)) and p.name not in ('ReceptorConcentrations.dat', 'Receptor_Timeseries_Transient.txt')}
    results = {}
    for label, extra in RUNS:
        comp = out / label / 'Computation'
        if comp.exists():
            shutil.rmtree(comp.parent)
        comp.mkdir(parents=True)
        for n in keep:
            shutil.copy2(SRC / n, comp / n)
        lines = (comp / 'in.dat').read_text(encoding='utf-8', errors='replace').splitlines()
        lines[21] = '1\t ! Use the GRAL reproducible results option Yes = 1, No = 0'
        (comp / 'in.dat').write_bytes(('\r\n'.join(lines) + '\r\n').encode('utf-8'))
        env = {k: v for k, v in os.environ.items() if not k.startswith(('INU_', 'GRAL_'))}
        env.update(INU_GPU_EXPERIMENTAL='1', INU_GPU_NVRTC_DIR=NVRTC, **extra)
        p = subprocess.run(['dotnet', str(DLL), str(comp)], cwd=comp, env=env, capture_output=True, timeout=1800)
        stdout = p.stdout.decode('utf8', 'replace')
        (out / label / 'stdout.log').write_text(stdout, encoding='utf-8')
        results[label] = {'rc': p.returncode, 'env': extra,
                          'device': [l for l in stdout.splitlines() if l.startswith('GPU device')][:1],
                          'fallback': [l for l in stdout.splitlines() if 'GPU fallback' in l or 'GPU startup' in l],
                          'deterministic': 'GRAL Deterministic Mode' in stdout,
                          'outputs': members(comp, keep)}
        print(label, 'rc', p.returncode, 'outputs', len(results[label]['outputs']), 'fb', len(results[label]['fallback']), flush=True)

    def diff(a, b):
        A, B = results[a]['outputs'], results[b]['outputs']
        return {'members_a': len(A), 'members_b': len(B), 'differing': sorted(k for k in set(A) | set(B) if A.get(k) != B.get(k))}
    summary = {'on1_vs_on2': diff('on1', 'on2'), 'off1_vs_off2': diff('off1', 'off2'), 'on1_vs_off1': diff('on1', 'off1')}
    for k, v in summary.items():
        print(k, 'members', v['members_a'], 'differing', len(v['differing']), v['differing'][:5])
    (out / 'gff_repeat.json').write_text(json.dumps({'runs': results, 'summary': summary}, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
