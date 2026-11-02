"""Prepare two declared 22-run mode cohorts without launching a model."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import fixtures

COHORTS=('transient_all_sources','steady_all_sources')
OFFSETS=(0,100000,200000,300000,400000,500000)
PROTOCOL='qa/statistical_protocol_new_modes.json'


def design(root: Path,cohort: str) -> list[dict]:
    if cohort not in COHORTS:raise ValueError('Unknown mode cohort.')
    runs=[]
    def pair(label,hours,offset,order,role,repeat):
        pair_id=f'{cohort}_{label}'
        for backend in order:
            run_id=f'{pair_id}_{backend}'
            runs.append(dict(run_id=run_id,cohort=cohort,fixture_case=cohort,hours=hours,
                             seed_offset=offset,backend=backend,pair_id=pair_id,role=role,
                             repeat=repeat,path=str(root/cohort/run_id)))
    for i,offset in enumerate(OFFSETS):
        pair(f'science24_s{offset}',24,offset,('cpu','gpu') if i%2==0 else ('gpu','cpu'),'science',0)
    for repeat,order in enumerate((('gpu','cpu'),('cpu','gpu')),1):
        pair(f'timing24_r{repeat}',24,0,order,'timing',repeat)
    for repeat,order in enumerate((('gpu','cpu'),('cpu','gpu'),('gpu','cpu'))):
        pair(f'timing48_r{repeat}',48,0,order,'timing',repeat)
    return runs


def write_new(path:Path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2)


def prepare(job:Path):
    destination=job/'study_manifest_new_modes.json';manifests=job/'study_manifests';root=job/'runs'/'study'
    if destination.exists() or manifests.exists() or root.exists():raise FileExistsError('New study paths must be empty.')
    protocol=job/PROTOCOL
    if not protocol.is_file():raise FileNotFoundError(protocol)
    manifests.mkdir()
    all_runs=[];cohort_files={}
    for cohort in COHORTS:
        rows=design(root,cohort)
        for row in rows:
            contract=fixtures.prepare(Path(row['path']),cohort,hours=row['hours'],particles_per_hour=360000,workers=16,schedule='constant')
            row['input_sha256']=contract['input_sha256']
        report=dict(schema=2,cohort=cohort,protocol=PROTOCOL,protocol_sha256=fixtures.sha(protocol),
                    status='prepared_not_executed',runs=rows,source_groups=[1,2,3,4],grid=[50,50],slice=1,
                    quiet_required_s=10,worker_count=16,affinity_logical_cpus=list(range(16,32)),
                    cache_condition='warm shared PTX; same-mode untimed four-situation GPU preparation required',
                    model_concurrency=1,physical_equivalence_not_established=True)
        path=manifests/f'{cohort}.json';write_new(path,report)
        cohort_files[cohort]=dict(path=str(path.relative_to(job)),sha256=fixtures.sha(path))
        all_runs.extend(rows)
    master=dict(schema=2,status='prepared_not_executed',protocol=PROTOCOL,protocol_sha256=fixtures.sha(protocol),
                cohorts=cohort_files,cohort_order=list(COHORTS),runs=all_runs,run_count=44,
                quiet_required_s=10,model_concurrency=1,prior_study_pooling=False)
    write_new(destination,master)
    print('[PREPARED] 44 runs; no models launched')
    return master


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True)
    prepare(parser.parse_args().job.resolve())
