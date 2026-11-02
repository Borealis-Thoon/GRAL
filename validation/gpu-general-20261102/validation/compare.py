"""Compare every GRZ member and receptor value without an acceptance threshold."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import zipfile
from pathlib import Path

MEMBER = re.compile(r'(\d{5})-(?:(\d)(\d+)\.con|(\d+)\.dep)')


def read_grid(payload: bytes) -> dict[tuple[int, int], float]:
    if len(payload) < 4:
        raise ValueError('truncated grid header')
    mode = struct.unpack_from('<i', payload)[0]
    if mode == -1:
        if (len(payload) - 4) % 12:
            raise ValueError('invalid sparse record length')
        records = struct.iter_unpack('<iif', memoryview(payload)[4:])
    elif mode == -3:
        if len(payload) < 28:
            raise ValueError('truncated dense grid header')
        header = struct.unpack_from('<iiiffii', payload)
        _, west, south, dx, dy, nx, ny = header
        if nx < 1 or ny < 1 or not all(math.isfinite(v) and v > 0 for v in (dx,dy)) or len(payload) != 28 + 4 * nx * ny:
            raise ValueError('invalid dense grid dimensions')
        values = struct.unpack_from('<' + str(nx * ny) + 'f', payload, 28)
        def center(index, spacing, origin):
            f32 = lambda value: struct.unpack('<f',struct.pack('<f',value))[0]
            value=f32(f32(f32((index+1)*spacing)-f32(spacing*.5))+origin)
            return math.floor(value+.5) if value >= 0 else math.ceil(value-.5)
        records = ((center(i,dx,west),center(j,dy,south),values[i*ny+j]) for i in range(nx) for j in range(ny))
    else:
        raise ValueError(f'unsupported grid encoding {mode}')
    grid = {}
    for x, y, value in records:
        if (x, y) in grid or not math.isfinite(value) or value < 0:
            raise ValueError('duplicate coordinate, negative or nonfinite grid value')
        grid[x, y] = value
    return grid


def ratio(a: float, b: float):
    return a / b if b else (0.0 if a == 0 else None)


def quantiles(values: list[float]) -> dict:
    seq = sorted(values)
    result = {}
    for q in (0., .25, .5, .75, .9, .95, .99, 1.):
        position = q * (len(seq) - 1)
        lo, hi = math.floor(position), math.ceil(position)
        result[str(q)] = (seq[lo] * (hi - position) + seq[hi] * (position - lo)
                          if hi != lo else seq[lo]) if seq else None
    return result


def metrics(reference, candidate) -> dict:
    a, b = list(reference), list(candidate)
    if len(a) != len(b) or any(not math.isfinite(v) or v < 0 for v in a + b):
        raise ValueError('shape mismatch or invalid comparison values')
    differences = [abs(x-y) for x, y in zip(a, b)]
    ref_sum, cand_sum = math.fsum(a), math.fsum(b)
    positive_pairs = [(x, y) for x, y in zip(a, b) if x > 0]
    positive_a, positive_b = [x for x in a if x > 0], [y for y in b if y > 0]
    union = sum(x > 0 or y > 0 for x, y in zip(a, b))
    return dict(equal=a == b, compared_values=len(a), different_values=sum(x != y for x, y in zip(a, b)),
                nmae=ratio(math.fsum(differences), ref_sum),
                normalized_bias=ratio(cand_sum-ref_sum, ref_sum),
                fac2_positive_reference=(sum(.5*x <= y <= 2*x for x, y in positive_pairs)/len(positive_pairs)
                                         if positive_pairs else None),
                fac2_denominator=len(positive_pairs), zero_zero_cells=sum(x == y == 0 for x, y in zip(a, b)),
                zero_reference_positive_candidate=sum(x == 0 < y for x, y in zip(a, b)),
                positive_reference_zero_candidate=sum(y == 0 < x for x, y in zip(a, b)),
                max_abs=max(differences, default=0), reference_sum=ref_sum, candidate_sum=cand_sum,
                reference_peak=max(a, default=0), candidate_peak=max(b, default=0),
                positive_support_jaccard=sum(x > 0 and y > 0 for x, y in zip(a, b))/union if union else 1.,
                reference_cell_quantiles=quantiles(a), candidate_cell_quantiles=quantiles(b),
                reference_positive_cell_quantiles=quantiles(positive_a), candidate_positive_cell_quantiles=quantiles(positive_b),
                absolute_error_quantiles=quantiles(differences))


def align(a: dict, b: dict) -> tuple[list, list]:
    coordinates = sorted(a.keys() | b.keys())
    return [a.get(k, 0.) for k in coordinates], [b.get(k, 0.) for k in coordinates]


def decode_text(path: Path) -> str:
    data = path.read_bytes()
    return data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')


def receptors(path: Path, hours: int) -> tuple[list, list, list, dict | None]:
    lines = decode_text(path).splitlines()
    if len(lines) < 5 + hours:
        raise ValueError(f'receptor row count mismatch: {path.name}')
    labels, values = [], []
    for line in lines[5:5+hours]:
        parts = line.rstrip('\t').split('\t')
        if len(parts) < 2:
            raise ValueError('empty receptor data row')
        labels.append(parts[0]); values.append([float(value) for value in parts[1:]])
    if not values or len({len(row) for row in values}) != 1:
        raise ValueError('inconsistent receptor columns')
    trailing = [line for line in lines[5+hours:] if line.strip()]
    footer = None
    if trailing:
        if len(trailing) != 1:
            raise ValueError('unexpected extra receptor rows')
        parts = trailing[0].rstrip('\t').split('\t')
        if not re.fullmatch(r'Est\. statistical error \[%\](?: SimulationSpan:\(1_'+str(hours)+r'\))?',parts[0]):
            raise ValueError('unrecognized receptor footer')
        if len(parts)-1 != len(values[0]):
            raise ValueError('receptor statistical-error column count mismatch')
        percentages=[]
        for value in parts[1:]:
            number = None if value == 'NA' else float(value.removesuffix('%'))
            if number is not None and (not value.endswith('%') or not math.isfinite(number) or number < 0):
                raise ValueError('invalid receptor statistical error')
            percentages.append(number)
        footer=dict(label=parts[0],statistical_error_percent=percentages,raw=trailing[0])
    return lines[:5], labels, values, footer


def compare_outputs(reference: Path, candidate: Path, *, hours: int,
                    expected_groups: tuple | None = None, slices: tuple = (1,),
                    deposition: bool = False, required_receptors: tuple = (),
                    expected_receptor_columns: int | None = None) -> dict:
    expected = {f'{hour:05d}.grz' for hour in range(1, hours+1)}
    if hours < 1 or {p.name for p in reference.glob('*.grz')} != expected or {p.name for p in candidate.glob('*.grz')} != expected:
        raise ValueError('missing or extra output hours')
    results = []
    all_equal = True
    per_hour = []
    for hour in range(1, hours+1):
        hour_fields = {}
        with zipfile.ZipFile(reference / f'{hour:05d}.grz') as za, zipfile.ZipFile(candidate / f'{hour:05d}.grz') as zb:
            an, bn = za.namelist(), zb.namelist()
            if not an or len(set(an)) != len(an) or len(set(bn)) != len(bn) or set(an) != set(bn):
                raise ValueError('missing, duplicate or unexpected ZIP members')
            if expected_groups is not None:
                wanted = {f'{hour:05d}-{s}{g:02d}.con' for s in slices for g in expected_groups}
                if deposition: wanted |= {f'{hour:05d}-{g:02d}.dep' for g in expected_groups}
                if set(an) != wanted or set(bn) != wanted:
                    raise ValueError('archive source group/slice/type set mismatch')
            for name in sorted(an):
                match = MEMBER.fullmatch(name)
                if not match or int(match[1]) != hour:
                    raise ValueError('unexpected archive member ' + name)
                raw_a, raw_b = za.read(name), zb.read(name)
                a, b = read_grid(raw_a), read_grid(raw_b)
                av, bv = align(a, b)
                equal = raw_a == raw_b
                all_equal &= equal
                extension = name.rsplit('.', 1)[1]
                row = dict(situation=hour, member=name, extension=extension,
                           slice=int(match[2]) if match[2] else None,
                           source_group=int(match[3] or match[4]), raw_equal=equal,
                           reference_sha256=hashlib.sha256(raw_a).hexdigest(),
                           candidate_sha256=hashlib.sha256(raw_b).hexdigest(), **metrics(av, bv))
                results.append(row)
                # Sum source groups within each slice and output type only.
                key = (extension, row['slice'])
                sums_a, sums_b = hour_fields.setdefault(key, ({}, {}))
                for k, v in a.items(): sums_a[k] = sums_a.get(k, 0.) + v
                for k, v in b.items(): sums_b[k] = sums_b.get(k, 0.) + v
        for (extension, slice_no), (a, b) in sorted(hour_fields.items(), key=lambda item: str(item[0])):
            av, bv = align(a, b)
            per_hour.append(dict(situation=hour, extension=extension, slice=slice_no, **metrics(av, bv)))
    receptor_names_a = {p.name for p in reference.glob('Receptor_*.txt') if 'Timeseries' in p.name}
    receptor_names_b = {p.name for p in candidate.glob('Receptor_*.txt') if 'Timeseries' in p.name}
    if receptor_names_a != receptor_names_b:
        raise ValueError('missing receptor output')
    if not set(required_receptors).issubset(receptor_names_a):
        raise ValueError('required receptor output is missing')
    receptor_results = []
    for name in sorted(receptor_names_a):
        ah, al, av, af = receptors(reference / name, hours)
        bh, bl, bv, bf = receptors(candidate / name, hours)
        if ah != bh or al != bl:
            raise ValueError('receptor metadata/time mismatch')
        if expected_receptor_columns is not None and (len(av[0]) != expected_receptor_columns or len(bv[0]) != expected_receptor_columns):
            raise ValueError('receptor concentration column count differs from contract')
        same = (reference / name).read_bytes() == (candidate / name).read_bytes()
        all_equal &= same
        receptor_results.append(dict(file=name, raw_equal=same, columns=len(av[0]),
            statistical_footer=dict(reference=af,candidate=bf,equal=af==bf),
            **metrics([v for row in av for v in row], [v for row in bv for v in row])))
    return dict(schema=1, hours=hours, members=results, per_hour=per_hour, receptors=receptor_results,
                raw_members_equal=all_equal, positive_concentration=any(row['reference_sum'] > 0 for row in results if row['extension'] == 'con'),
                acceptance='unassigned; apply predeclared protocol separately',
                definitions=dict(nmae='sum(abs(candidate-reference))/sum(reference)',
                    normalized_bias='sum(candidate-reference)/sum(reference)',
                    fac2='0.5*reference <= candidate <= 2*reference, reference>0; zero-zero excluded',
                    quantiles='linear interpolation over aligned union coordinates; positive-only also reported',
                    spatial_sums='concentration sums are diagnostics, not emitted-mass conservation'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--hours', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--input-manifest', type=Path, help='defaults to reference parent/input_manifest.json')
    args = p.parse_args()
    manifest_path = args.input_manifest or args.reference.parent/'input_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['hours'] != args.hours:
        raise ValueError('comparison hour count differs from input contract')
    config = manifest['config']
    required = ('Receptor_Timeseries_Transient.txt',) if config.get('receptors') else ()
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(compare_outputs(args.reference, args.candidate, hours=args.hours, expected_groups=(1,2,3),
                                  deposition=config.get('deposition',False),required_receptors=required,
                                  expected_receptor_columns=config['receptors']*3 if config.get('receptors') else None),out,indent=2,allow_nan=False)


if __name__ == '__main__':
    main()
