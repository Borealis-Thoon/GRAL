"""Read-only postprocessing for source-group boundaries and measured repeat fidelity."""
from pathlib import Path
import argparse
from collections import defaultdict
import hashlib
import itertools
import json
import re
import struct
import zipfile
import numpy as np

DEFAULT_JOB = Path(__file__).resolve().parents[2]
PAYLOAD_SUFFIXES = ('.con', '.dep')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_fingerprint(folder):
    items = [(p.relative_to(folder).as_posix(), sha256(p)) for p in sorted(folder.rglob('*')) if p.is_file() and p.name != 'case.json']
    return hashlib.sha256(json.dumps(items, separators=(',', ':')).encode()).hexdigest()


def arrays(folder, wanted=None):
    """Read recorded V03 payloads only. Never run the model or alter inputs."""
    result = {}
    for path in sorted(folder.glob('*.grz')):
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                key = path.name + ':' + name
                if not name.endswith(PAYLOAD_SUFFIXES) or (wanted is not None and key not in wanted):
                    continue
                raw = archive.read(name)
                assert len(raw) >= 28, (path, name, 'short header')
                h, x, y, dx, dy, nx, ny = struct.unpack_from('<iiiffii', raw)
                assert h == -3 and nx > 0 and ny > 0 and len(raw) == 28 + nx * ny * 4, (path, name, 'V03 shape')
                values = np.frombuffer(raw[28:], dtype='<f4').copy()
                assert np.isfinite(values).all() and (values >= 0).all(), (path, name, 'invalid values')
                result[key] = values
    if wanted is not None:
        assert set(result) == wanted, (folder, 'missing requested payloads', sorted(wanted - set(result)))
    return result


def payload_hashes(record, suffix):
    return {k: v for k, v in record.get('payload_hashes', {}).items() if k.endswith(suffix)}


def compare_records(reference, variant, suffix):
    a = payload_hashes(reference, suffix)
    b = payload_hashes(variant, suffix)
    if set(a) != set(b) or not a:
        return dict(comparable=False, reference_fields=len(a), variant_fields=len(b))
    keys = {k for k in a if a[k] != b[k]}
    condition = reference['_condition']
    count = condition['nx'] * condition['ny'] * len(a)
    if not keys:
        return dict(comparable=True, fields=len(a), values=count, payload_hashes_equal=True, exact_values=True, changed_values=0, sum_abs=0.0, relative_l1=0.0, max_abs=0.0, decoded_fields=0)
    av = arrays(reference['_folder'], keys)
    bv = arrays(variant['_folder'], keys)
    changed = 0
    total_abs = max_abs = 0.0
    for key in keys:
        x = av[key].astype(np.float64)
        y = bv[key].astype(np.float64)
        diff = np.abs(x - y)
        changed += int(np.count_nonzero(diff))
        total_abs += float(diff.sum())
        max_abs = max(max_abs, float(diff.max(initial=0)))
    if suffix == '.con':
        # The benchmark records concentration-only sums for every weather step.
        denominator = sum(reference.get('situation_sums', {}).values())
        if not reference.get('situation_sums'):
            denominator = sum(float(v.sum(dtype=np.float64)) for v in arrays(reference['_folder'], set(a)).values())
    else:
        denominator = sum(float(v.sum(dtype=np.float64)) for v in arrays(reference['_folder'], set(a)).values())
    return dict(comparable=True, fields=len(a), values=count, payload_hashes_equal=False, exact_values=changed == 0, changed_values=changed, sum_abs=total_abs, reference_sum=denominator, relative_l1=total_abs / denominator if denominator else (0.0 if total_abs == 0 else None), max_abs=max_abs, decoded_fields=len(keys))


def brief(record):
    return {key: record.get(key) for key in ['tag', 'case', 'variant', 'repeat', 'measured', 'status', 'exit_code', 'issues', 'error'] if key in record}


def reasons(folder):
    answer = []
    for name in ['Problemreport_GRAL.txt', 'console.log', 'stderr.log']:
        path = folder / name
        if path.exists():
            lines = path.read_text(encoding='utf-8-sig', errors='replace').splitlines()
            chosen = [line.strip() for line in lines if re.search(r'error|exception|receptor|stopped|source groups|source group', line, re.I)]
            answer.extend(dict(file=name, text=line[:400]) for line in chosen[:15])
    return answer


def group_statistics(record):
    condition = record['_condition']
    labels = condition.get('labels', list(range(1, condition['sg'] + 1)))
    expected = {}
    for weather in range(1, condition['situations'] + 1):
        for label in labels:
            for height in range(1, condition['slices'] + 1):
                name = f'{weather:05d}-{height}{label:02d}.con'
                assert name not in expected, ('ambiguous filename', name)
                expected[name] = (label, weather, height)
    totals = {str(label): dict(sum=0.0, nonzero=0, values=0, fields=0) for label in labels}
    fields = []
    for key, values in arrays(record['_folder'], set(payload_hashes(record, '.con'))).items():
        name = key.split(':', 1)[1]
        assert name in expected, (name, 'unexpected group label')
        label, weather, height = expected[name]
        item = dict(label=label, weather=weather, height=height, sum=float(values.sum(dtype=np.float64)), nonzero=int(np.count_nonzero(values)), values=int(values.size))
        fields.append(item)
        total = totals[str(label)]
        for metric in ['sum', 'nonzero', 'values']:
            total[metric] += item[metric]
        total['fields'] += 1
    return dict(group_count=condition['sg'], input_labels=labels, group_totals=totals, fields=fields)


def collect(job):
    result = []
    for record_path in sorted((job / 'results').glob('*/records.json')):
        run = record_path.parent
        completion = run / 'completion.json'
        assert completion.exists() and read_json(completion).get('completed'), ('unfinished run', run)
        for raw in read_json(record_path):
            record = dict(raw, tag=run.name)
            folder = run / 'runs' / f"{raw['case']}_{raw['variant']}_{raw['repeat']}"
            inputs = run / 'inputs' / raw['case']
            record['_folder'] = folder
            record['_condition'] = read_json(inputs / 'case.json')
            record['_input_fingerprint'] = input_fingerprint(inputs)
            result.append(record)
    return result


def is_boundary(record):
    c = record['_condition']
    return record['tag'].startswith('boundaries') or bool(c.get('labels')) or bool(c.get('expected_boundary')) or 'missing_receptor' in record['case']


def analyze(job):
    records = collect(job)
    boundary_records = [r for r in records if is_boundary(r)]
    assert boundary_records, 'boundaries run not found'
    boundary = []
    for record in boundary_records:
        item = brief(record)
        item['input_labels'] = record['_condition'].get('labels', list(range(1, record['_condition']['sg'] + 1)))
        item['group_count'] = record['_condition']['sg']
        item['diagnostic_log_lines'] = reasons(record['_folder'])
        if record.get('payload_hashes'):
            item['concentration_by_group'] = group_statistics(record)
        if record['case'] == 'labels_1_257' and 'concentration_by_group' in item:
            totals = item['concentration_by_group']['group_totals']
            item['observed_alias_pattern'] = totals['1']['sum'] > 0 and totals['257']['sum'] == 0
            item['interpretation'] = 'Observed label-1 concentration and zero label-257 concentration; source inspection separately identifies byte truncation 257 -> 1.'
        boundary.append(item)
    receptor = []
    by_boundary = {(r['tag'], r['case'], r['variant'], r['repeat']): r for r in boundary_records}
    for record in boundary_records:
        if 'missing_receptor' not in record['case'] or record['variant'] == 'double':
            continue
        reference = by_boundary.get((record['tag'], record['case'], 'double', record['repeat']))
        if reference:
            ref_sum = sum(reference.get('situation_sums', {}).values())
            new_sum = sum(record.get('situation_sums', {}).values())
            receptor.append(dict(record=brief(record), reference=brief(reference), total_concentration_sum=new_sum, reference_total_concentration_sum=ref_sum, retained_fraction=new_sum / ref_sum if ref_sum else None, concentration=compare_records(reference, record, '.con')))
    deposition = []
    for group in itertools.groupby(sorted([r for r in records if r['_condition'].get('deposition')], key=lambda r: (r['tag'], r['case'], r['repeat'])), key=lambda r: (r['tag'], r['case'], r['repeat'])):
        key, members = group
        variants = {r['variant']: r for r in members}
        if 'double' not in variants:
            continue
        for variant, record in variants.items():
            if variant == 'double':
                continue
            deposition.append(dict(tag=key[0], case=key[1], repeat=key[2], variant=variant, reference_status=variants['double']['status'], variant_status=record['status'], concentration=compare_records(variants['double'], record, '.con'), deposition=compare_records(variants['double'], record, '.dep')))
    groups = defaultdict(list)
    for record in records:
        if not record.get('measured') or record['status'] != 'pass' or is_boundary(record):
            continue
        groups[(record['case'], record['variant'], record['_input_fingerprint'])].append(record)
    repeat_groups = []
    for (case, variant, fingerprint), members in sorted(groups.items()):
        pairs = []
        for a, b in itertools.combinations(members, 2):
            pair = dict(reference=dict(tag=a['tag'], repeat=a['repeat']), variant=dict(tag=b['tag'], repeat=b['repeat']), concentration=compare_records(a, b, '.con'))
            if payload_hashes(a, '.dep') or payload_hashes(b, '.dep'):
                pair['deposition'] = compare_records(a, b, '.dep')
            pairs.append(pair)
        repeat_groups.append(dict(case=case, variant=variant, input_fingerprint=fingerprint, measured_runs=len(members), pairs=pairs))
    evidence = dict(
        source_group_count=dict(source='All four input readers allocate emission_sourcegroup[101], indexed by internal group index.', native_status={case: {r['variant']: r['status'] for r in boundary_records if r['case'] == case} for case in ['sg101_boundary', 'sg102_boundary', 'sg108_boundary']}),
        source_group_label=dict(source='WriteLogFiles.LogfileGralCoreInfo indexes DecayRate by the external label; ProgramDeclarations initializes DecayRate as double[102]. Valid array indices are 0..101.', supersedes='The native DecayRate boundary supersedes earlier source-only suggestions that byte-sized labels through 255 are usable end to end. Historical source-review notes are retained unchanged.', native_status={case: {r['variant']: r['status'] for r in boundary_records if r['case'] == case} for case in sorted({r['case'] for r in boundary_records if r['_condition'].get('labels')})}, original_failure_stack='System.IndexOutOfRangeException in ProgramWriters.LogfileGralCoreInfo; optimized Release trace points to method entry, while the last emitted line is Computing pollutant NOx and source inspection identifies DecayRate[sg].', alias_evidence='Byte truncation of labels above 255 is a source-level additional risk. Native labels 1/257 produce no concentration output because the logging array fails first; native aliasing was not reproduced.'),
        missing_receptor=dict(evidence_level='native input-error diagnostic', qualification='All variants report the missing receptor input. Original dictionary writes zero total concentration; compare actual figures in missing_receptor_comparisons. This is excluded from valid-input performance results.', supersedes='The earlier source-only D03 assessment in qa/final_review_notes.json is superseded by this native diagnostic.'),
        direct_writer=dict(evidence_level='compiled writer/internal-key test', qualification='Reflection directly initializes arrays and dictionaries, bypassing input readers and byte particle-label storage. Its index/label 300 success does not prove native group or label support.')
    )
    repeat_summary = []
    for g in repeat_groups:
        c = [p['concentration'] for p in g['pairs'] if p['concentration'].get('comparable')]
        repeat_summary.append(dict(case=g['case'], variant=g['variant'], measured_runs=g['measured_runs'], compared_pairs=len(c), all_values_exact=all(p['exact_values'] for p in c), max_relative_l1=max((p['relative_l1'] or 0.0 for p in c), default=0.0), max_absolute=max((p['max_abs'] for p in c), default=0.0), max_changed_values=max((p['changed_values'] for p in c), default=0)))
    return dict(evidence_levels=evidence, measured_repeat_summary=repeat_summary, analysis_status='complete', method='Recorded outputs only; concentration and deposition metrics are separate; measured-repeat pairs exclude warmups and invalid boundary inputs; unchanged payload hashes avoid decoding.', source=Path(__file__).name, source_sha256=sha256(Path(__file__)), record_count=len(records), boundary_record_count=len(boundary_records), boundary_records=boundary, missing_receptor_comparisons=receptor, deposition_comparisons=deposition, measured_repeat_groups=repeat_groups, performance_exclusions=[brief(r) for r in records if is_boundary(r) or r['status'] != 'pass'], qualifications=['Direct writer/internal-key tests do not establish input-reader support for the same numeric labels or group counts.', 'Boundary and missing-input diagnostics are excluded from performance evidence even if a process exits successfully.', 'Concentration and deposition exactness may be combined, but relative L1 is never combined across their different quantities.', 'The existing benchmark compares repeats to warmup; this report independently compares measured repeats only.'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', type=Path, default=DEFAULT_JOB)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    job = args.job.resolve()
    report = analyze(job)
    output = args.output or job / 'qa' / 'boundary_repeat_analysis.json'
    save_json(output, report)
    print('[ANALYSIS]', len(report['boundary_records']), 'boundary records', len(report['measured_repeat_groups']), 'repeat groups')


if __name__ == '__main__':
    main()


