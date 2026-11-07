"""GRZ member identity of a HIP build's 16-case outputs against the earlier HIP build (build_hip3) outputs.

Usage: compare_identity.py <new build name> <out json> [old build name, default build_hip3]
Also compares receptor/deposition text outputs present in both Computation folders (raw bytes).
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

JOB = Path(__file__).resolve().parents[1]
new, out = sys.argv[1], Path(sys.argv[2])
old = sys.argv[3] if len(sys.argv) > 3 else 'build_hip3'


def members(folder):
    res = {}
    for grz in sorted(folder.glob('*.grz')):
        with zipfile.ZipFile(grz) as z:
            for n in z.namelist():
                res[grz.name + '/' + n] = hashlib.sha256(z.read(n)).hexdigest()
    for txt in sorted(folder.glob('*.txt')):
        if txt.name.startswith(('Receptor', 'Deposition')):  # transient receptor and deposition outputs (none in the 16 study cases)
            res[txt.name] = hashlib.sha256(txt.read_bytes()).hexdigest()
    return res


result = {}
for nd in sorted((JOB / 'smoke').glob(f'*_fixed00_{new}')):
    case = nd.name.split('_')[0]
    od = JOB / 'smoke' / f'{case}_fixed00_{old}'
    if not od.exists():
        result[case] = {'error': 'no old output'}
        continue
    a, b = members(od / 'Computation'), members(nd / 'Computation')
    diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    result[case] = {'members_old': len(a), 'members_new': len(b), 'differing': len(diff), 'first_differing': diff[:6]}
    print(case, result[case]['members_old'], result[case]['members_new'], 'differing', len(diff), diff[:3])
out.write_text(json.dumps(result, indent=1), encoding='utf8')
