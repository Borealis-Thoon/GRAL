"""Run the synthetic functional matrix serially; no performance claims."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import compare
import fixtures
import run_matrix


def compare_case(a: Path,b: Path,manifest: dict) -> dict:
    required=('Receptor_Timeseries_Transient.txt',) if manifest['config'].get('receptors') else ()
    return compare.compare_outputs(a/'Computation',b/'Computation',hours=manifest['hours'],
        expected_groups=tuple(manifest.get('source_groups', (1,2,3))),deposition=manifest['config'].get('deposition',False),required_receptors=required,
        expected_receptor_columns=manifest['config']['receptors']*len(manifest.get('source_groups', (1,2,3))) if manifest['config'].get('receptors') else None)


def run_case(args,name: str) -> dict:
    manifests={}; results={}; targets={}
    for mode in ('cpu','gpu'):
        target=args.out/(name+'_'+mode)
        manifests[mode]=fixtures.prepare(target,name)
        targets[mode]=target
        trial=copy.copy(args);trial.target=target;trial.mode=mode;trial.seed_offset=0;trial.no_quiet=True
        results[mode]=run_matrix.run_one(trial)
        print('[FUNCTIONAL]',name,mode,results[mode]['status'],flush=True)
        if results[mode]['status']!='pass':
            return dict(case=name,status='fail',runs=results)
    if manifests['cpu']['input_sha256']!=manifests['gpu']['input_sha256']:
        raise ValueError('paired inputs differ')
    comparison=compare_case(targets['cpu'],targets['gpu'],manifests['cpu'])
    run_matrix.write_new(args.out/(name+'_comparison.json'),comparison)
    if name=='nonfixed_seed':
        status='pass_dispatch_completion_only'
    elif manifests['cpu']['config']['dispatch']=='fallback' and not comparison['raw_members_equal']:
        # A third explicit CPU run measures CPU repeatability instead of relaxing equality.
        target=args.out/(name+'_cpu_repeat')
        fixtures.prepare(target,name)
        trial=copy.copy(args);trial.target=target;trial.mode='cpu';trial.seed_offset=0;trial.no_quiet=True
        results['cpu_repeat']=run_matrix.run_one(trial)
        if results['cpu_repeat']['status']!='pass':
            status='fail'
        else:
            repeatability=compare_case(targets['cpu'],target,manifests['cpu'])
            run_matrix.write_new(args.out/(name+'_cpu_repeatability.json'),repeatability)
            status='cpu_repeatability_review_required' if not repeatability['raw_members_equal'] else 'fail_fallback_parity'
    else:
        status='pass'
    return dict(case=name,status=status,runs=results,comparison_file=name+'_comparison.json',
                raw_members_equal=comparison['raw_members_equal'],
                inference='no numerical scientific acceptance threshold applied to functional smoke')


def run(args) -> dict:
    args.out.mkdir(parents=True,exist_ok=False)
    reports=[]
    for name in args.cases:
        report=run_case(args,name)
        reports.append(report)
        run_matrix.write_new(args.out/(name+'_result.json'),report)
        if report['status'].startswith('fail'):
            break
    if args.bare_dll is not None and not any(r['status'].startswith('fail') for r in reports):
        target=args.out/'area_bare_cpu'
        manifest=fixtures.prepare(target,'area')
        bare=copy.copy(args);bare.target=target;bare.dll=args.bare_dll;bare.mode='cpu';bare.seed_offset=0;bare.no_quiet=True
        bare_result=run_matrix.run_one(bare)
        row=dict(case='overlay_offset0_vs_bare_cpu',status=bare_result['status'],bare_run=bare_result)
        if bare_result['status']=='pass':
            compared=compare_case(target,args.out/'area_cpu',manifest)
            run_matrix.write_new(args.out/'overlay_offset0_vs_bare_cpu.json',compared)
            row['raw_members_equal']=compared['raw_members_equal']
            row['status']='pass' if compared['raw_members_equal'] else 'cpu_repeatability_review_required'
        reports.append(row)
    failed=any(r['status'].startswith('fail') for r in reports)
    review=any('review_required' in r['status'] for r in reports)
    summary=dict(schema=1,status='fail' if failed else ('review_required' if review else 'pass'),
                 cases=reports,synthetic_only=True,timing_eligible=False,
                 expected_cases=args.cases,completed_cases=[r['case'] for r in reports],
                 measured_study_started=False)
    run_matrix.write_new(args.out/'functional_summary.json',summary)
    print('[MATRIX]',summary['status'],len(reports),flush=True)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--dll',type=Path,required=True)
    p.add_argument('--bare-dll',type=Path)
    p.add_argument('--gpu-python',type=Path,default=Path(run_matrix.sys.executable))
    p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--nvrtc-dir',type=Path,required=True)
    p.add_argument('--dependencies',type=Path)
    p.add_argument('--cache',type=Path)
    p.add_argument('--timeout',type=int,default=1200)
    p.add_argument('--cases',nargs='+',choices=fixtures.CASES,default=list(fixtures.CASES))
    a=p.parse_args()
    if a.bare_dll is not None and 'area' not in a.cases:
        p.error('--bare-dll requires area in --cases')
    result=run(a)
    raise SystemExit(0 if result['status']=='pass' else (2 if result['status']=='review_required' else 1))
