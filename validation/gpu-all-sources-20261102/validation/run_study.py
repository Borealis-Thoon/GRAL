"""Freeze and run the approved 22 synthetic trials in declared serial order."""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import subprocess
from pathlib import Path

import fixtures
import prepare_study
import run_matrix
from support import runtime_helpers


def hashes(root: Path, *, source: bool = False) -> dict:
    return {str(p.relative_to(root)).replace('\\','/'): fixtures.sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and (not source or not set(p.relative_to(root).parts).intersection({'.git','bin','obj','__pycache__'}))}


def scripts() -> dict:
    root=Path(__file__).parent
    paths=sorted(root.glob('*.py'))+sorted((root/'support').glob('*.py'))
    return {str(p.relative_to(root)).replace('\\','/'):fixtures.sha(p) for p in paths}


def verify_snapshot(root: Path, fingerprints: dict):
    for name,digest in fingerprints.items():
        if fixtures.sha(root/name)!=digest: raise ValueError('frozen file changed: '+str(root/name))


def validate_manifest(manifest: dict, job: Path) -> list[dict]:
    rows=manifest['runs']
    expected=prepare_study.design(job/'runs'/'study')
    if len(rows)!=22: raise ValueError('study requires exactly22 runs')
    for row,wanted in zip(rows,expected):
        if {k:row.get(k) for k in wanted}!=wanted:
            raise ValueError('manifest order/condition differs from predeclared design')
        target=Path(row['path'])
        contract=json.loads((target/'input_manifest.json').read_text(encoding='utf-8'))
        if contract['hours']!=row['hours'] or contract['particles_per_hour']!=360000 or contract['workers']!=16 or contract['case']!='supported_primary':
            raise ValueError('primary synthetic fixture contract mismatch')
        if contract['input_sha256']!=row['input_sha256'] or fixtures.input_hashes(target)!=row['input_sha256']:
            raise ValueError('prepared input hash mismatch')
        if (target/'logs').exists(): raise ValueError('study run already launched; automatic reruns are forbidden')
        if contract['factors']!=[[1,1,1]]*row['hours']:
            raise ValueError('primary source factors must be constant1,1,1')
    for pair_id in {r['pair_id'] for r in rows}:
        twins=[r for r in rows if r['pair_id']==pair_id]
        if len(twins)!=2 or twins[0]['input_sha256']!=twins[1]['input_sha256']:
            raise ValueError('paired CPU/GPU input files are not identical')
    return rows


def freeze(args, manifest: dict) -> dict:
    job=args.manifest.resolve().parent
    protocol=job/manifest['protocol']
    if fixtures.sha(protocol)!=manifest['protocol_sha256']:
        raise ValueError('statistical protocol differs from prepared manifest')
    warm=json.loads(args.warmup_receipt.read_text(encoding='utf-8'))
    if warm.get('status')!='pass': raise ValueError('functional/warmup receipt is not pass')
    cases={r['case']:r for r in warm['cases']}
    required=set(fixtures.CASES)|{'overlay_offset0_vs_bare_cpu'}
    if set(cases)!=required or len(warm['cases'])!=len(required):
        raise ValueError('functional receipt does not cover every required case and bare control')
    for name in fixtures.CASES:
        record=cases[name]
        if not record['status'].startswith('pass') or set(record['runs'])!={'cpu','gpu'}:
            raise ValueError('functional case failed or is incomplete: '+name)
        if any(result.get('status')!='pass' for result in record['runs'].values()):
            raise ValueError('functional backend failed: '+name)
        if fixtures.CASES[name]['dispatch']=='fallback' and name!='nonfixed_seed' and record.get('raw_members_equal') is not True:
            raise ValueError('fixed-seed CPU fallback parity is not exact: '+name)
    control=cases['overlay_offset0_vs_bare_cpu']
    if control['status']!='pass' or control.get('raw_members_equal') is not True:
        raise ValueError('offset-zero overlay does not reproduce bare CPU output exactly')
    gpu_runs=[r['runs']['gpu'] for r in warm['cases'] if r.get('case')=='supported_primary' and 'runs' in r]
    if len(gpu_runs)!=1 or gpu_runs[0]['status']!='pass' or gpu_runs[0]['quiet_gate_enabled']:
        raise ValueError('untimed supported-primary GPU preparation is missing')
    if not args.cache.is_dir() or not any(args.cache.rglob('*.json')):
        raise ValueError('warm PTX cache is missing')
    runtime={name:fixtures.sha(args.runtime/name) for name in run_matrix.RUNTIME_FILES}
    build=runtime_helpers.build_hashes(args.dll.parent)
    if gpu_runs[0]['runtime_hashes']!=runtime or gpu_runs[0]['build_hashes']!=build:
        raise ValueError('warmup used a different GPU runtime or binary build')
    cached=[]
    for path in args.cache.glob('*.json'):
        entry=json.loads(path.read_text(encoding='utf-8'))
        if entry.get('schema')!=1 or entry.get('key')!=path.stem or not isinstance(entry.get('ptx'),str) or entry.get('size',0)<=1:
            raise ValueError('invalid warmed PTX cache entry')
        cached.append(dict(file=path.name,sha256=fixtures.sha(path)))
    if not cached: raise ValueError('warm PTX cache has no recognized entries')
    probe=json.loads(args.seed_probe.read_text(encoding='utf-8-sig'))
    if probe.get('status')!='pass' or probe.get('checked_states')!=288 or probe.get('offsets')!=[0,100000,200000,300000,400000,500000]:
        raise ValueError('actual-constructor reflection probe is missing or incomplete')
    for offset in probe['offsets']:
        states=[r for r in probe['states'] if r['offset']==offset]
        if [r['situation'] for r in states]!=list(range(1,49)):
            raise ValueError('reflection seed probe has missing situations')
        for state in states:
            shifted=state['situation']+offset
            if (state['seed1'],state['seed2'])!=(521288629+200+4*shifted,2232121+2*shifted):
                raise ValueError('actual constructor reflection state differs from fixture formula')
    source_head=subprocess.run(['git','-C',str(args.source),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    records=dict(schema=1,created=datetime.datetime.now().astimezone().isoformat(),
        manifest_sha256=fixtures.sha(args.manifest),protocol_sha256=fixtures.sha(protocol),
        protocol_markdown_sha256=fixtures.sha(protocol.with_suffix('.md')),
        warmup_receipt_sha256=fixtures.sha(args.warmup_receipt),
        source_sha256=hashes(args.source,source=True),overlay_source_sha256=hashes(args.overlay_source,source=True),
        binary_sha256=build,runtime_sha256=runtime,
        nvrtc_sha256=hashes(args.nvrtc_dir),script_sha256=scripts(),
        cache_condition='predeclared warm; same shared PTX cache as completed untimed primary functional',
        cache_path=str(args.cache.resolve()),sample_targets_s=dict(process=.1,device_gpu=.2),
        offsets=[0,100000,200000,300000,400000,500000])
    records['warmed_ptx_cache_entries']=cached
    records['seed_probe_sha256']=fixtures.sha(args.seed_probe)
    records['source_git_head']=source_head
    return records


def check_frozen(args, frozen: dict):
    if fixtures.sha(args.manifest)!=frozen['manifest_sha256']:
        raise ValueError('study manifest changed')
    protocol=args.manifest.parent/'qa'/'statistical_protocol.json'
    if fixtures.sha(protocol)!=frozen['protocol_sha256']:
        raise ValueError('statistical protocol changed')
    if fixtures.sha(protocol.with_suffix('.md'))!=frozen['protocol_markdown_sha256']:
        raise ValueError('detailed statistical protocol changed')
    if fixtures.sha(args.warmup_receipt)!=frozen['warmup_receipt_sha256']:
        raise ValueError('functional receipt changed')
    if fixtures.sha(args.seed_probe)!=frozen['seed_probe_sha256']:
        raise ValueError('actual seed probe changed')
    current_head=subprocess.run(['git','-C',str(args.source),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    if current_head!=frozen['source_git_head']: raise ValueError('source git commit changed')
    for root,key in ((args.source,'source_sha256'),(args.overlay_source,'overlay_source_sha256'),
                     (args.dll.parent,'binary_sha256'),(args.runtime,'runtime_sha256'),(args.nvrtc_dir,'nvrtc_sha256')):
        verify_snapshot(root,frozen[key])
    if scripts()!=frozen['script_sha256']:
        raise ValueError('validation scripts changed during frozen cohort')


def validate_prefixes(completed: list[dict]):
    all_seeds={}
    for row in completed:
        result=row['result']
        if result['observer'].get('status')!='pass': raise ValueError('measured run lacks mandatory observer')
        seed_rows=result['observer']['seed_rows']
        if [r['IWET'] for r in seed_rows]!=list(range(1,row['hours']+1)):
            raise ValueError('measured seed row situation range mismatch')
        for seed in seed_rows:
            if (seed['WindVelGral'],seed['WindDirGral'],seed['TAUS'],seed['fixed_mode'])!=(2,0,3600,True):
                raise ValueError('primary fixture actual wind, duration or fixed-seed mode changed')
            shifted=seed['IWET']+row['seed_offset']
            if (seed['Seed1'],seed['Seed2'])!=(521288629+200+4*shifted,2232121+2*shifted):
                raise ValueError('actual seed does not match the primary fixture constructor formula')
        seeds=[(r['Seed1'],r['Seed2']) for r in seed_rows]
        key=(row['seed_offset'],row['backend'])
        if key in all_seeds:
            old=all_seeds[key]
            if old[:min(len(old),len(seeds))]!=seeds[:min(len(old),len(seeds))]:
                raise ValueError('same offset has a different24/48h seed prefix')
        else: all_seeds[key]=seeds
    for offset in {r['seed_offset'] for r in completed}:
        cpu=all_seeds.get((offset,'cpu'));gpu=all_seeds.get((offset,'gpu'))
        if cpu is not None and gpu is not None and cpu[:min(len(cpu),len(gpu))]!=gpu[:min(len(cpu),len(gpu))]:
            raise ValueError('CPU/GPU seed twins differ')
    firsts=[seeds[0] for (offset,backend),seeds in all_seeds.items() if backend=='cpu']
    if len(firsts)!=len(set(firsts)): raise ValueError('different offsets have duplicated actual RNG states')


def run(args) -> dict:
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    job=args.manifest.resolve().parent
    with runtime_helpers.reservation(job/'COHORT.lock'):
        rows=validate_manifest(manifest,job)
        frozen=freeze(args,manifest)
        if args.preflight_only:
            check_frozen(args,frozen)
            run_matrix.write_new(job/'qa'/'harness_study_preflight.json',dict(status='pass',run_count=22,**frozen))
            return dict(status='preflight_pass_no_models_launched',run_count=0)
        run_matrix.write_new(job/'qa'/'harness_study_freeze.json',frozen)
        completed=[]
        try:
            for row in rows:
                check_frozen(args,frozen)
                print('[STUDY_START]',row['run_id'],flush=True)
                trial=copy.copy(args)
                trial.target=Path(row['path']);trial.mode=row['backend'];trial.seed_offset=row['seed_offset'];trial.no_quiet=False
                result=run_matrix.run_one(trial)
                completed.append(dict(row,result=result))
                print('[STUDY_END]',row['run_id'],result['status'],flush=True)
                if result['status']!='pass': raise ValueError('study run failed: '+row['run_id'])
                if row['backend']=='gpu':
                    initial=result['dispatch']['metrics'][0].get('init_server',{}).get('metrics_cumulative',{})
                    if initial.get('cache_status')!='hit':
                        raise ValueError('measured GPU run did not use the predeclared warm PTX cache')
                validate_prefixes(completed)
                check_frozen(args,frozen)
            report=dict(schema=1,status='pass',run_count=len(completed),runs=completed,
                        science_acceptance='pending independent analysis',frozen_receipt='qa/harness_study_freeze.json')
        except BaseException as exc:
            report=dict(schema=1,status='fail',run_count=len(completed),runs=completed,error=repr(exc),
                        automatic_rerun=False,frozen_receipt='qa/harness_study_freeze.json')
            run_matrix.write_new(job/'qa'/'harness_study_results.json',report)
            raise
        run_matrix.write_new(job/'qa'/'harness_study_results.json',report)
        return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--dll',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--overlay-source',type=Path,required=True)
    p.add_argument('--warmup-receipt',type=Path,required=True)
    p.add_argument('--seed-probe',type=Path,required=True)
    p.add_argument('--preflight-only',action='store_true')
    p.add_argument('--gpu-python',type=Path,default=Path(run_matrix.sys.executable))
    p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--nvrtc-dir',type=Path,required=True)
    p.add_argument('--dependencies',type=Path)
    p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--timeout',type=int,default=7200)
    a=p.parse_args()
    report=run(a)
    print('[STUDY]',report['status'],report['run_count'])
