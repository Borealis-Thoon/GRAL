"""Compare GRZ concentration outputs of two runs (cell by cell over every member).

Usage: compare_grz.py <ref Computation folder> <test Computation folder> [<test dx> <test dy>]
Prints one JSON line: sum_abs_diff, sum_abs_ref, relative, max_abs_diff, members, identical members, and the
relative difference of the top-1 % cell values (mean of the largest 1 % of cell values, all members pooled).
"""
import json
import struct
import sys
import zipfile
from pathlib import Path

import numpy as np


def read(folder, dx=0, dy=0):
    """Members of every GRZ; dx, dy are subtracted from the record coordinates (to compare a shifted case)."""
    out = {}
    for grz in sorted(Path(folder).glob('*.grz')):
        with zipfile.ZipFile(grz) as z:
            for n in z.namelist():
                b = z.read(n)
                if len(b) < 4 or struct.unpack('<i', b[:4])[0] != -1:
                    raise ValueError(f'unexpected member header {grz.name}/{n}')
                rec = np.frombuffer(b, dtype=[('x', '<i4'), ('y', '<i4'), ('v', '<f4')], offset=4)
                out[grz.name + '/' + n] = (b, {(int(x) - dx, int(y) - dy): float(v) for x, y, v in rec})
    return out


def main():
    shift = [int(v) for v in sys.argv[3:5]] if len(sys.argv) > 4 else [0, 0]
    ref, test = read(sys.argv[1]), read(sys.argv[2], *shift)
    if set(ref) != set(test):
        raise SystemExit(f'member sets differ: {len(set(ref) ^ set(test))}')
    sad = sar = 0.0
    mx = 0.0
    same = 0
    rv, tv = [], []
    for k in ref:
        rb, r = ref[k]
        tb, t = test[k]
        same += rb == tb
        for key in r.keys() | t.keys():
            a, b = r.get(key, 0.0), t.get(key, 0.0)
            d = abs(a - b)
            sad += d
            sar += abs(a)
            mx = max(mx, d)
            rv.append(a)
            tv.append(b)
    rv, tv = np.array(rv), np.array(tv)
    q = max(1, len(rv) // 100)
    top_r = np.sort(rv)[-q:].mean()
    top_t = np.sort(tv)[-q:].mean()
    print(json.dumps({'sum_abs_diff': sad, 'sum_abs_ref': sar, 'relative': sad / sar if sar else None,
                      'max_abs_diff': mx, 'members': len(ref), 'identical_members': same, 'cells': len(rv),
                      'top1pct_rel_diff': (top_t - top_r) / top_r, 'sum_rel_diff': (tv.sum() - rv.sum()) / rv.sum()}))


if __name__ == '__main__':
    main()
