"""Copy the B00 fixed-seed inputs and move the whole case to real-world coordinates.

Usage: shift_case.py <out folder> [dx dy] [native]   (default dx=150000, dy=430000 m, inside the Incheon EPSG:5181 range)
Shifted: GRAL.geb and GRAMM.geb extents, the GRAMM origin stored in ggeom.asc, and every source coordinate
(cadastre.dat, line.dat, point.dat, portals.dat). Wind fields and terrain are index based and stay as they are.
'native' also sets in.dat line 22 to 0 (no fixed seed). The out folder gets Computation/, Weather/ and an input_manifest.json in the smoke_pinvoke.py format.
"""
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

SRC = Path(r'<jobs>\20261103_gral_gpu_final_validation\runs\final448_001\targets\B00_fixed00_cpu')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def shift_csv(path, header_lines, xy_columns, dx, dy):
    lines = path.read_text(encoding='utf8').splitlines()
    out = lines[:header_lines]
    for line in lines[header_lines:]:
        if not line.strip():
            out.append(line)
            continue
        cells = line.split(',')
        for c, d in xy_columns:
            cells[c] = repr(float(cells[c]) + (dx if d == 'x' else dy)).removesuffix('.0')
        out.append(','.join(cells))
    path.write_text('\r\n'.join(out) + '\r\n', encoding='utf8', newline='')


def shift_geb(path, first, dx, dy):
    """Lines first..first+3 hold west, east, south, north."""
    lines = path.read_text(encoding='utf8').splitlines()
    for k, d in zip(range(first, first + 4), (dx, dx, dy, dy)):
        lines[k] = str(int(lines[k]) + d)
    path.write_text('\r\n'.join(lines) + '\r\n', encoding='utf8', newline='')


def shift_ggeom(path, dx, dy):
    """Binary ggeom.asc as read by ReadGgeomAsc.cs; GRAMM west/south are two Int32 after the DDX..ZAY arrays."""
    b = bytearray(path.read_bytes())
    ni, nj, nk = struct.unpack_from('<3i', b, 6)
    nx, ny, nz = ni, nj, nk
    off = 6 + 12
    off += 4 * ni * nj                      # AH
    off += 4 * nk * nj * ni                 # ZSP
    off += 4 * ((ni + 1) + (nj + 1) + (nk + 1))   # XKO, YKO, ZKO
    off += 4 * nz * ny * nx                 # VOL
    off += 4 * nz * ny * (nx + 1)           # AREAX
    off += 4 * nz * (ny + 1) * nx           # AREAY
    off += 4 * 3 * (nz + 1) * ny * nx       # three (NZ+1) x NY x NX blocks
    off += 4 * (ni + nj + ni + nj)          # DDX, DDY and two unused arrays
    west, south = struct.unpack_from('<2i', b, off)
    angle = struct.unpack_from('<d', b, off + 8)[0]
    rest = len(b) - (off + 16)
    if (west, south, angle) != (0, 0, 0.0) or rest != 4 * (nk + 1) * (nj + 1) * (ni + 1):
        raise ValueError(f'unexpected ggeom layout: west={west} south={south} angle={angle} rest={rest}')
    struct.pack_into('<2i', b, off, west + dx, south + dy)
    path.write_bytes(bytes(b))
    return off


def main():
    out = Path(sys.argv[1])
    nums = [a for a in sys.argv[2:] if a != 'native']
    dx, dy = (int(nums[0]), int(nums[1])) if len(nums) > 1 else (150000, 430000)
    manifest = json.loads((SRC / 'input_manifest.json').read_text(encoding='utf8'))
    out.mkdir(parents=True, exist_ok=False)
    for name in manifest['input_sha256']:
        d = out / name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SRC / name, d)
    c = out / 'Computation'
    shift_geb(c / 'GRAL.geb', 7, dx, dy)
    shift_geb(c / 'GRAMM.geb', 3, dx, dy)
    ggeom_offset = shift_ggeom(c / 'ggeom.asc', dx, dy)
    shift_csv(c / 'cadastre.dat', 1, [(0, 'x'), (1, 'y')], dx, dy)
    shift_csv(c / 'line.dat', 5, [(3, 'x'), (4, 'y'), (6, 'x'), (7, 'y')], dx, dy)
    shift_csv(c / 'point.dat', 2, [(0, 'x'), (1, 'y')], dx, dy)
    shift_csv(c / 'portals.dat', 2, [(0, 'x'), (1, 'y'), (2, 'x'), (3, 'y')], dx, dy)
    if 'native' in sys.argv[2:]:
        lines = (c / 'in.dat').read_bytes().split(b'\n')
        if lines[21].strip() != b'1':
            raise ValueError('in.dat line 22 is not the fixed-seed flag 1')
        lines[21] = b'0'
        (c / 'in.dat').write_bytes(b'\n'.join(lines))
        manifest['seed_control']['mode'] = 'random'
    manifest['input_sha256'] = {name: sha(out / name) for name in manifest['input_sha256']}
    manifest['seed_control']['offset'] = 0
    manifest['shift_m'] = [dx, dy]
    manifest['shifted_from'] = str(SRC)
    (out / 'input_manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf8')
    print(json.dumps({'out': str(out), 'shift_m': [dx, dy], 'ggeom_origin_offset': ggeom_offset}))


if __name__ == '__main__':
    main()
