"""Decode actual GRAL writer output and compare the four source variants."""
import argparse
import hashlib
import json
import pathlib
import struct
import subprocess


def decode(record):
    data = bytes.fromhex(record['hex'])
    h, = struct.unpack_from('<i', data)
    width = 4 if record['category'] == 'odour' else 1
    result = {'header': h, 'cells': []}
    pos = 4
    if h == -1:
        while pos < len(data):
            x, y = struct.unpack_from('<ii', data, pos)
            pos += 8
            values = list(struct.unpack_from('<' + 'f' * width, data, pos))
            pos += 4 * width
            result['cells'].append({'x': x, 'y': y, 'values': values})
    elif h in (-2, -3):
        ox, oy, dx, dy = struct.unpack_from('<iiff', data, pos)
        pos += 16
        result['origin'] = [ox, oy]
        result['spacing'] = [dx, dy]
        if h == -2:
            while True:
                count, = struct.unpack_from('<i', data, pos)
                pos += 4
                if count == -1:
                    break
                assert count > 0 and count % width == 0
                i, j = struct.unpack_from('<ii', data, pos)
                pos += 8
                for offset in range(count // width):
                    values = list(struct.unpack_from('<' + 'f' * width, data, pos))
                    pos += 4 * width
                    result['cells'].append({'i': i, 'j': j + offset, 'values': values})
        else:
            nx, ny = struct.unpack_from('<ii', data, pos)
            pos += 8
            result['grid'] = [nx, ny]
            for i in range(1, nx + 1):
                for j in range(1, ny + 1):
                    values = list(struct.unpack_from('<' + 'f' * width, data, pos))
                    pos += 4 * width
                    if any(v != 0 for v in values):
                        result['cells'].append({'i': i, 'j': j, 'values': values})
    else:
        raise ValueError(h)
    assert pos == len(data), (pos, len(data))
    return result


def run(job):
    qa = job / 'qa' / 'edge_checks'
    variants = ['float', 'double', 'dictionary', 'dictionary_fixed']
    raw = {v: json.loads((qa / (v + '.json')).read_text()) for v in variants}
    decoded = {v: [dict(r, decoded=decode(r)) for r in raw[v]['records']] for v in variants}
    comparisons = {}
    for v in variants:
        details = []
        for base, current in zip(decoded['double'], decoded[v], strict=True):
            identity = ('category', 'name', 'method', 'header', 'group', 'slice')
            assert all(base[k] == current[k] for k in identity)
            details.append({**{k: base[k] for k in identity}, 'bytes_equal': base['hex'] == current['hex'], 'decoded_equal': base['decoded'] == current['decoded'], 'base_length': base['length'], 'variant_length': current['length'], 'base_decoded': base['decoded'], 'variant_decoded': current['decoded']})
        comparisons[v] = {'count': len(details), 'byte_mismatches': sum(not d['bytes_equal'] for d in details), 'decoded_mismatches': sum(not d['decoded_equal'] for d in details), 'details': details, 'residual_retention': raw[v]['retention']}
    evidence = {}
    needles = {
        'src/ProgramFunctions.cs': ['private static void ParallelParticleDriver', 'Program.Concentration2D.Clear();'],
        'src/Program.cs': ['ParallelTransientParticleDriver(0, cellNr)', 'ParallelParticleDriver(1, NTEILMAX + 1)'],
        'src/Write2DConcentrations.cs': ['private static bool WriteOdourData', 'if (Program.Conz3d[i][j][II][IQ] != 0)', 'if (Program.TempConcArray[i][j] != 0)', 'Program.Concentration2D.TryGetValue', 'Program.Concentration2D.Clear();'],
    }
    for v in variants:
        work = job / 'work' / v
        files = {}
        for rel, strings in needles.items():
            path = work / rel
            content = path.read_bytes()
            lines = content.decode('utf-8-sig').splitlines()
            matches = [{'line': index, 'text': line.strip()} for index, line in enumerate(lines, 1) if any(needle in line for needle in strings)]
            files[rel] = {'sha256': hashlib.sha256(content).hexdigest(), 'matches': matches}
        commit = subprocess.check_output(['git', '-C', str(work), 'rev-parse', 'HEAD'], text=True).strip()
        evidence[v] = {'head': commit, 'assembly_sha256': raw[v]['assembly_sha256'], 'files': files}
    result = {'method': 'Actual compiled GRAL methods invoked via reflection; no reimplemented writer or particle driver is used to produce output.', 'odour_masks': {'0': 'none', '1': 'center only', '2': 'upper only', '3': 'center and upper', '4': 'lower only', '5': 'center and lower', '6': 'upper and lower', '7': 'all three'}, 'writer_cases_per_variant': 84, 'odour_cases_per_variant': 24, 'concentration_cases_per_variant': 30, 'grz_entries_per_variant': 30, 'source_group_ids': [99,108,255,256,300], 'source_group_indices': [0,1,255,256,300], 'comparisons_against_double': comparisons, 'source_evidence': evidence}
    (qa / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    for variant, comparison in comparisons.items():
        print(variant, 'records', comparison['count'], 'mismatches', comparison['byte_mismatches'], 'retained', [r['before'] == r['after'] for r in comparison['residual_retention']])
    assert comparisons['float']['byte_mismatches'] == 0
    assert comparisons['dictionary']['byte_mismatches'] == 12
    assert comparisons['dictionary_fixed']['byte_mismatches'] == 0
    assert all(r['before'] == r['after'] for r in comparisons['double']['residual_retention'])
    assert all(r['after'] == 0 for r in comparisons['dictionary']['residual_retention'])
    assert all(r['before'] == r['after'] for r in comparisons['dictionary_fixed']['residual_retention'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('job', type=pathlib.Path)
    run(parser.parse_args().job.resolve())
