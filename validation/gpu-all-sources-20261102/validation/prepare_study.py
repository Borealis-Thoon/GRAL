"""Freeze the approved 22-run design and prepare synthetic inputs only."""
import argparse
import json
from pathlib import Path

import fixtures


def design(root: Path) -> list[dict]:
    runs = []
    def pair(pair_id, hours, offset, order, role, repeat):
        for backend in order:
            run_id = pair_id + '_' + backend
            runs.append(dict(run_id=run_id, fixture_case='supported_primary', hours=hours,
                             seed_offset=offset, backend=backend, pair_id=pair_id, role=role,
                             repeat=repeat, path=str(root/run_id)))
    for i, offset in enumerate((0,100000,200000,300000,400000,500000)):
        pair(f'science24_s{offset}',24,offset,('cpu','gpu') if i%2==0 else ('gpu','cpu'),'science',0)
    for repeat, order in enumerate((('gpu','cpu'),('cpu','gpu')),1):
        pair(f'timing24_r{repeat}',24,0,order,'timing',repeat)
    for repeat, order in enumerate((('gpu','cpu'),('cpu','gpu'),('gpu','cpu'))):
        pair(f'timing48_r{repeat}',48,0,order,'timing',repeat)
    if len(runs)!=22 or len({r['run_id'] for r in runs})!=22:
        raise AssertionError('invalid cohort design')
    return runs


def prepare(job: Path):
    destination=job/'study_manifest.json'
    if destination.exists(): raise FileExistsError(destination)
    root=job/'runs'/'study'
    if root.exists(): raise FileExistsError(root)
    runs=design(root)
    for row in runs:
        manifest=fixtures.prepare(Path(row['path']),row['fixture_case'],hours=row['hours'],particles_per_hour=360000,schedule='constant')
        row['input_sha256']=manifest['input_sha256']
    report=dict(schema=1,protocol='qa/statistical_protocol.json',protocol_sha256=fixtures.sha(job/'qa'/'statistical_protocol.json'),
                status='prepared_not_executed',runs=runs,source_groups=[1,2,3],grid=[50,50],slice=1,
                cache_condition='warm shared cache; untimed GPU preparation must precede measured cohort',
                worker_count=16,affinity_logical_cpus=list(range(16,32)),model_concurrency=1,
                comparison_scope='engineering synthetic fixture; physical equivalence not established')
    with destination.open('x',encoding='utf-8') as stream: json.dump(report,stream,indent=2)
    print('[PREPARED] 22 runs; no models launched')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--job',type=Path,required=True)
    prepare(p.parse_args().job.resolve())
