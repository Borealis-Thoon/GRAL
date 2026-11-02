"""Package reviewed synthetic-study evidence; never launch a model."""
from __future__ import annotations
import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

JOB = Path(__file__).resolve().parent.parent
DEST = JOB / 'publication' / 'support'
STAGING = JOB / 'publication' / 'support__staging'
HEAD = 'b60673164b749896c3b942d0e89753addc1c6f7b'
COHORTS = ('transient_all_sources', 'steady_all_sources')
OBSERVER_ROOT = JOB.parent / '20261102_gral_gpu_final_optimized' / 'candidate'
OBSERVER = OBSERVER_ROOT / 'src' / 'BenchmarkTelemetry.cs'
EXCLUDED = {'.git', 'bin', 'obj', '__pycache__', 'ptx_cache', 'build', 'cache'}
BAD_SUFFIXES = {'.exe', '.dll', '.pdb', '.ptx', '.pyc'}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def within(path, root):
    path, root = Path(path).absolute(), Path(root).absolute()
    if not path.is_relative_to(root):
        raise ValueError(f'Path outside root: {path}')
    current = path
    while True:
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise ValueError(f'Linked component: {current}')
        if current == root:
            break
        current = current.parent
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve(strict=True)):
        raise ValueError(f'Redirected path: {path}')
    return resolved


def study_input_files(manifest):
    """Select exact portable-path run files for pre/post-analysis snapshots."""
    selected = {}
    for row in manifest['runs']:
        cohort, run_id = row['cohort'], row['run_id']
        if cohort not in COHORTS or Path(run_id).name != run_id:
            raise ValueError('Invalid cohort or run identifier')
        root = within(Path(row['path']), JOB / 'runs' / 'study')
        if root != (JOB / 'runs' / 'study' / cohort / run_id).resolve():
            raise ValueError('Run path does not match cohort and identifier')
        base = Path('runs/study') / cohort / run_id
        paths = [root / 'input_manifest.json']
        paths.extend(root / name for name in read(root / 'input_manifest.json')['input_sha256'])
        paths.extend(sorted((root / 'Computation').glob('*.grz')))
        paths.extend(p for p in sorted((root / 'logs').iterdir()) if p.is_file() and p.suffix.lower() in {'.json', '.jsonl', '.csv', '.log', '.txt', '.stderr'})
        for path in paths:
            within(path, root)
            relative = (base / path.relative_to(root)).as_posix()
            if relative in selected:
                raise ValueError(f'Duplicate run file: {relative}')
            selected[relative] = path
    return selected


def main():
    manifest_path = JOB / 'study_manifest_new_modes.json'
    freeze_path = JOB / 'qa/harness_new_modes_study_freeze.json'
    results_path = JOB / 'qa/harness_new_modes_study_results.json'
    review_path = JOB / 'qa/final_review.json'
    snapshot_path = JOB / 'qa/analysis_inputs_manifest.json'
    within(JOB / 'publication', JOB)
    if DEST.exists() or STAGING.exists():
        raise FileExistsError('Final or staging evidence directory exists')
    manifest, freeze, results = read(manifest_path), read(freeze_path), read(results_path)
    rows = manifest['runs']
    ids = [r['run_id'] for r in rows]
    if len(rows) != 44 or len(set(ids)) != 44 or manifest['run_count'] != 44:
        raise ValueError('Expected 44 distinct runs')
    if tuple(manifest['cohort_order']) != COHORTS or set(manifest['cohorts']) != set(COHORTS):
        raise ValueError('Unexpected cohorts')
    if results.get('status') != 'pass' or results.get('run_count') != 44:
        raise ValueError('Study is incomplete')
    completed = results['runs']
    if len(completed) != 44 or [r['run_id'] for r in completed] != ids:
        raise ValueError('Study receipt run order differs')
    if any({k: v for k, v in done.items() if k != 'result'} != row or done['result'].get('status') != 'pass' for row, done in zip(rows, completed)):
        raise ValueError('Study receipt differs from manifest or has failed run')
    head = subprocess.run(['git', '-C', str(JOB / 'repo'), 'rev-parse', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()
    if head != HEAD or freeze['source_git_head'] != HEAD or sha(manifest_path) != freeze['manifest_sha256']:
        raise ValueError('Source or master manifest differs from freeze')
    for root, key in ((JOB / 'repo', 'source_sha256'), (JOB / 'validation/benchmark_repo_v2', 'overlay_source_sha256'), (JOB / 'validation', 'script_sha256'), (JOB / 'analysis', 'analysis_script_sha256')):
        for name, expected in freeze[key].items():
            path = root / name
            within(path, root)
            if sha(path) != expected:
                raise ValueError(f'Frozen source changed: {path}')
    protocol = JOB / 'qa/statistical_protocol_new_modes.json'
    if sha(protocol) != freeze['protocol_sha256'] or sha(protocol.with_suffix('.md')) != freeze['protocol_markdown_sha256']:
        raise ValueError('Frozen protocol changed')
    if sha(JOB / 'qa/harness_seed_probe.json') != freeze['seed_probe_sha256'] or sha(JOB / 'runs/functional_v2/functional_summary.json') != freeze['warmup_receipt_sha256']:
        raise ValueError('Frozen seed or functional receipt changed')
    overlay = read(JOB / 'qa/harness_overlay_v2.json')
    if sha(OBSERVER) != overlay['original_observer_sha256']:
        raise ValueError('Original observer hash differs')
    analyses, cohort_manifests = {}, {}
    for cohort in COHORTS:
        cohort_path = JOB / 'study_manifests' / f'{cohort}.json'
        cohort_manifest = read(cohort_path)
        subset = [r for r in rows if r['cohort'] == cohort]
        if len(subset) != 22 or cohort_manifest['runs'] != subset or cohort_manifest['cohort'] != cohort:
            raise ValueError(f'Invalid cohort rows: {cohort}')
        if sha(cohort_path) != freeze['cohort_manifest_sha256'][cohort] or sha(cohort_path) != manifest['cohorts'][cohort]['sha256']:
            raise ValueError(f'Cohort manifest changed: {cohort}')
        cohort_manifests[cohort] = cohort_manifest
        analysis = JOB / 'analysis/measured' / cohort
        within(analysis, JOB / 'analysis')
        summary, artifacts = read(analysis / 'analysis_summary.json'), read(analysis / 'artifact_sha256.json')
        if summary.get('status') != 'analyzed_pending_review' or summary.get('cohort') != cohort or summary.get('study_sha256') != sha(cohort_path):
            raise ValueError(f'Analysis does not bind cohort: {cohort}')
        if summary.get('analysis_source_sha256') != freeze['analysis_script_sha256']:
            raise ValueError(f'Analysis scripts differ from freeze: {cohort}')
        measurements = summary['run_measurements']
        if len(measurements) != 22 or set(r['run_id'] for r in measurements) != {r['run_id'] for r in subset}:
            raise ValueError(f'Analysis measurements differ: {cohort}')
        if not isinstance(artifacts, dict) or 'analysis_summary.json' not in artifacts or not any(Path(n).as_posix().startswith('figures/') and n.endswith('.png') for n in artifacts):
            raise ValueError(f'Invalid analysis artifacts: {cohort}')
        for name, expected in artifacts.items():
            path = analysis / name
            within(path, analysis)
            if sha(path) != expected:
                raise ValueError(f'Analysis artifact changed: {path}')
        analyses[cohort] = (analysis, summary, artifacts)
    review_sha256 = sha(review_path)
    review = read(review_path)
    if sha(review_path) != review_sha256:
        raise ValueError('Review changed while reading')
    bindings = {'source_head': HEAD, 'study_manifest_sha256': sha(manifest_path),
                'study_freeze_sha256': sha(freeze_path), 'study_results_sha256': sha(results_path),
                'analysis_inputs_manifest_sha256': sha(snapshot_path),
                'cohorts': {c: {'study_manifest_sha256': sha(JOB / 'study_manifests' / f'{c}.json'),
                                 'analysis_summary_sha256': sha(analyses[c][0] / 'analysis_summary.json'),
                                 'artifact_manifest_sha256': sha(analyses[c][0] / 'artifact_sha256.json'),
                                 'analysis_source_sha256': analyses[c][1]['analysis_source_sha256']} for c in COHORTS}}
    if review.get('status') != 'pass' or any(review.get(k) != v for k, v in bindings.items()):
        raise ValueError('Review receipt is not bound to these artifacts')
    if not review.get('claims') or not review.get('scope') or not review.get('limits'):
        raise ValueError('Review receipt must state claims, scope and limits')
    if any(review.get(k) is not True for k in ('analysis_inputs_manifest_before_after_equal', 'formal_equivalence_not_tested')):
        raise ValueError('Missing reviewed input equality or inference limits')

    files = {}
    def add(src, target, root=JOB):
        src, target = Path(src), Path(target)
        within(src, root)
        if not src.is_file() or any(p.lower() in EXCLUDED for p in src.parts) or src.suffix.lower() in BAD_SUFFIXES:
            raise ValueError(f'Invalid or excluded file: {src}')
        if target.is_absolute() or '..' in target.parts or target in files:
            raise ValueError(f'Invalid destination: {target}')
        files[target] = src

    selected = study_input_files(manifest)
    snapshot = read(snapshot_path)
    if set(snapshot) != set(selected):
        raise ValueError('Snapshot selection differs from run files')
    for row, done in zip(rows, completed):
        root = Path(row['path'])
        measurement = next(r for r in analyses[row['cohort']][1]['run_measurements'] if r['run_id'] == row['run_id'])
        result = root / 'logs/result.json'
        if read(result) != done['result'] or sha(result) != measurement['result_sha256'] or sha(root / 'input_manifest.json') != measurement['input_manifest_sha256']:
            raise ValueError(f'Run result differs: {row["run_id"]}')
        inputs = read(root / 'input_manifest.json')['input_sha256']
        if inputs != row['input_sha256']:
            raise ValueError(f'Run input manifest differs: {row["run_id"]}')
        for name, digest in inputs.items():
            within(root / name, root)
            if sha(root / name) != digest:
                raise ValueError(f'Run input changed: {name}')
        if {p.name for p in (root / 'Computation').glob('*.grz')} != {f'{n:05d}.grz' for n in range(1, row['hours'] + 1)}:
            raise ValueError(f'GRZ set differs: {row["run_id"]}')
        required = {'result.json', 'process_telemetry.csv', 'gpu_telemetry.csv', 'process_memory.jsonl', 'stdout.log', 'stderr.log', 'timing.jsonl'}
        if row['backend'] == 'gpu': required.add('gpu_metrics.jsonl')
        if not required.issubset({p.name for p in (root / 'logs').iterdir() if p.is_file()}):
            raise ValueError(f'Run logs incomplete: {row["run_id"]}')
    for name, src in selected.items():
        if sha(src) != snapshot[name]:
            raise ValueError(f'Snapshot changed: {name}')
        add(src, Path(name))
    for directory, suffixes in ((JOB / 'tests/NewModeDispatch', {'.cs', '.csproj'}),
                                 (JOB / 'tests/SourceSeriesReader', {'.cs', '.csproj'}),
                                 (JOB / 'tests/GpuDispatch/HostContracts', {'.cs', '.csproj'}),
                                 (JOB / 'validation/seed_probe', {'.cs', '.csproj'}),
                                 (JOB / 'translator', {'.cs', '.csproj', '.cuh'})):
        for path in sorted(directory.rglob('*')):
            if path.is_file() and path.suffix.lower() in suffixes and not set(p.lower() for p in path.parts).intersection(EXCLUDED):
                add(path, path.relative_to(JOB))
    for name in freeze['script_sha256']:
        add(JOB / 'validation' / name, Path('validation') / name)
    for name in freeze['analysis_script_sha256']:
        add(JOB / 'analysis' / name, Path('analysis') / name)
    add(OBSERVER, Path('validation/observer/BenchmarkTelemetry.cs'), OBSERVER_ROOT)
    qa_names = ('statistical_protocol_new_modes.json', 'statistical_protocol_new_modes.md',
                'harness_new_modes_study_freeze.json', 'harness_new_modes_study_preflight.json',
                'harness_new_modes_study_results.json', 'harness_seed_probe.json', 'harness_overlay_v2.json',
                'implementation_new_modes.json', 'csharp_new_modes_review.json', 'csharp_new_modes_review.md',
                'python_new_modes_review.json', 'python_new_modes_review.md', 'runtime_environment.json',
                'new_mode_baseline_host.json', 'new_mode_candidate_host_v2.json',
                'source_series_finite_green_v2.json', 'csharp_probe_result.json',
                'final_review.json', 'analysis_inputs_manifest.json',
                'scientific_result_review.json', 'scientific_result_review.md', 'independent_scientific_review.py', 'independent_raw_review.json',
                'publication_python_review.json', 'publication_python_review.md',
                'analysis_inputs_before.json', 'analysis_inputs_after.json', 'visual_review.json', 'prose_review.json')
    for name in qa_names:
        add(JOB / 'qa' / name, Path('qa') / name)
    add(JOB / 'publication/package_evidence.py', Path('publication/package_evidence.py'))
    add(JOB / 'publication/PACKAGING_PLAN.md', Path('publication/PACKAGING_PLAN.md'))
    add(JOB / 'docs/evidence_README.md', Path('README.md'))
    for name in ('optimization_and_scope.md', 'runtime_setup.md'):
        add(JOB / 'docs' / name, Path('docs') / name)
    add(manifest_path, Path('provenance/study_manifest_new_modes.original.json'))
    cases = ('area', 'area_line_switch', 'area_receptor1', 'buildings', 'decay', 'dry_deposition', 'flat',
             'line_horizontal', 'line_vertical', 'mixed_point_area', 'nonfixed_seed', 'point_buoyant',
             'point_cold_momentum', 'point', 'point_portal_timeseries', 'portal', 'receptors51',
             'steady_all_sources', 'steady_area', 'steady_line', 'steady_point', 'steady_portal',
             'supported_primary', 'transient_all_sources')
    functional = JOB / 'runs/functional_v2'
    for name in ('functional_summary.json', 'overlay_offset0_vs_bare_cpu.json') + tuple(f'{case}_{kind}.json' for case in cases for kind in ('result', 'comparison')):
        add(functional / name, Path('functional_v2') / name)
    for cohort, (analysis, summary, artifacts) in analyses.items():
        add(JOB / 'study_manifests' / f'{cohort}.json', Path('provenance') / f'{cohort}.original.json')
        add(analysis / 'artifact_sha256.json', Path('analysis/measured') / cohort / 'artifact_sha256.json')
        for name in artifacts:
            add(analysis / name, Path('analysis/measured') / cohort / name)

    # Bind copied bytes to the already reviewed and frozen hashes.
    expected = {
        manifest_path: bindings['study_manifest_sha256'], freeze_path: bindings['study_freeze_sha256'],
        results_path: bindings['study_results_sha256'], snapshot_path: bindings['analysis_inputs_manifest_sha256'],
        review_path: review_sha256, protocol: freeze['protocol_sha256'],
        protocol.with_suffix('.md'): freeze['protocol_markdown_sha256'],
        JOB / 'qa/harness_seed_probe.json': freeze['seed_probe_sha256'],
        JOB / 'runs/functional_v2/functional_summary.json': freeze['warmup_receipt_sha256'],
        OBSERVER: overlay['original_observer_sha256'],
    }
    for name, digest in freeze['script_sha256'].items(): expected[JOB / 'validation' / name] = digest
    for name, digest in freeze['analysis_script_sha256'].items(): expected[JOB / 'analysis' / name] = digest
    for cohort, (analysis, summary, artifacts) in analyses.items():
        binding = bindings['cohorts'][cohort]
        expected[JOB / 'study_manifests' / f'{cohort}.json'] = binding['study_manifest_sha256']
        expected[analysis / 'analysis_summary.json'] = binding['analysis_summary_sha256']
        expected[analysis / 'artifact_sha256.json'] = binding['artifact_manifest_sha256']
        for name, digest in artifacts.items(): expected[analysis / name] = digest
    for name, src in selected.items(): expected[src] = snapshot[name]
    STAGING.mkdir()
    inventory = {}
    for target, src in sorted(files.items(), key=lambda item: item[0].as_posix()):
        out = STAGING / target
        out.parent.mkdir(parents=True, exist_ok=True)
        before = sha(src)
        if src in expected and before != expected[src]:
            raise ValueError(f'Validated source changed before copy: {src}')
        with src.open('rb') as source, out.open('xb') as destination:
            shutil.copyfileobj(source, destination, length=1024 * 1024)
        if before != sha(src) or before != sha(out):
            raise IOError(f'Changed during copy: {src}')
        if target.as_posix() in snapshot and before != snapshot[target.as_posix()]:
            raise IOError(f'Copied run input differs from snapshot: {src}')
        inventory[target.as_posix()] = before
    rewrites = []
    public_hashes = {}
    for cohort in COHORTS:
        public = copy.deepcopy(cohort_manifests[cohort])
        for row in public['runs']:
            old = row['path']
            row['path'] = (Path('../runs/study') / cohort / row['run_id']).as_posix()
            rewrites.append({'manifest': cohort, 'run_id': row['run_id'], 'field': 'path', 'from': old, 'to': row['path']})
        public['protocol'] = '../qa/statistical_protocol_new_modes.json'
        path = STAGING / 'study_manifests' / f'{cohort}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(public, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        public_hashes[cohort] = sha(path)
        inventory[path.relative_to(STAGING).as_posix()] = public_hashes[cohort]
    public = copy.deepcopy(manifest)
    for row in public['runs']:
        old = row['path']
        row['path'] = (Path('runs/study') / row['cohort'] / row['run_id']).as_posix()
        rewrites.append({'manifest': 'master', 'run_id': row['run_id'], 'field': 'path', 'from': old, 'to': row['path']})
    public['protocol'] = 'qa/statistical_protocol_new_modes.json'
    for cohort in COHORTS:
        public['cohorts'][cohort]['path'] = f'study_manifests/{cohort}.json'
        public['cohorts'][cohort]['sha256'] = public_hashes[cohort]
    path = STAGING / 'study_manifest_new_modes.public.json'
    path.write_text(json.dumps(public, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    inventory[path.name] = sha(path)
    attributes = STAGING / '.gitattributes'
    attributes.write_bytes(b'* -text\n')
    inventory[attributes.name] = sha(attributes)
    provenance = {'source_head': head, 'original_master_sha256': sha(manifest_path),
                  'original_cohort_sha256': freeze['cohort_manifest_sha256'], 'public_cohort_sha256': public_hashes,
                  'run_path_rewrites': rewrites, 'protocol_rewritten_relative': True,
                  'master_cohort_paths_and_sha256_rewritten_for_public_manifests': True,
                  'raw_logs_rewritten': False, 'functional_scope': 'Summary and case JSON only; raw functional runs excluded.',
                  'analysis_review_receipt': 'qa/final_review.json',
                  'implementation_new_modes_scope': 'Historical initial implementation receipt; its initial hashes are not current source proof. See the frozen source hashes.'}
    path = STAGING / 'provenance/bundle_provenance.json'
    path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    inventory[path.relative_to(STAGING).as_posix()] = sha(path)
    (STAGING / 'MANIFEST_SHA256.json').write_text(json.dumps(dict(sorted(inventory.items())), indent=2) + '\n', encoding='utf-8')
    STAGING.rename(DEST)
    print(f'[PACKAGED] {len(inventory)} files: {DEST}')


if __name__ == '__main__':
    main()
