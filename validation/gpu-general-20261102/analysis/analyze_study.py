"""Analyze the frozen GRAL virtual-fixture protocol; never launch model runs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import itertools
import json
import math
import struct
from pathlib import Path

import numpy as np

SEED_OFFSETS = [0, 100000, 200000, 300000, 400000, 500000]
SOURCE_LABELS = {'1': 'AREA', '2': 'Horizontal LINE', '3': 'Vertical LINE', 'aggregate': 'Aggregate'}


def ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else (0. if numerator == 0 else math.copysign(math.inf, numerator))


def valid_field(value) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 3 or array.size == 0 or not np.all(np.isfinite(array)) or np.any(array < 0):
        raise ValueError('Expected finite nonnegative field [hour,x,y].')
    return array


def field_metrics(reference, candidate) -> dict:
    """Equal cell areas and equal one-hour intervals, as fixed in this fixture."""
    x, y = valid_field(reference), valid_field(candidate)
    if x.shape != y.shape:
        raise ValueError('Field shapes differ.')
    diff = y - x
    mx, my = float(x.mean()), float(y.mean())
    scale = (mx + my) / 2
    xmap, ymap = x.mean(axis=0), y.mean(axis=0)
    constant = np.ptp(xmap) == 0 or np.ptp(ymap) == 0
    result = {
        'values': int(x.size), 'hours': int(x.shape[0]),
        'mean_cpu': mx, 'mean_gpu': my,
        'L': float(np.abs(diff).mean()),
        'mean_difference': my - mx,
        'weighted_nmae': ratio(float(np.abs(diff).mean()), scale),
        'normalized_bias': ratio(my - mx, scale),
        'spatial_pearson': None if constant else float(np.corrcoef(xmap.ravel(), ymap.ravel())[0,1]),
        'spatial_pearson_reason': 'constant_map' if constant else None,
        'zero_status': 'both_zero' if scale == 0 else 'positive_reference_scale',
        'max_absolute_difference': float(np.abs(diff).max()),
        'cpu_max': float(x.max()), 'gpu_max': float(y.max()),
        'cpu_max_index_hour0_x0_y0': [int(v) for v in np.unravel_index(np.argmax(x),x.shape)],
        'gpu_max_index_hour0_x0_y0': [int(v) for v in np.unravel_index(np.argmax(y),y.shape)],
    }
    for q in (.95,.99):
        a, b = float(np.quantile(x,q,method='linear')), float(np.quantile(y,q,method='linear'))
        result[f'p{int(q*100)}'] = {'cpu':a,'gpu':b,'difference':b-a,'absolute_difference':abs(b-a)}
    return result


def aggregate_groups(groups: dict[str,np.ndarray]) -> dict[str,np.ndarray]:
    if not groups or 'aggregate' in groups:
        raise ValueError('Expected source groups without a precomputed aggregate.')
    values = [valid_field(v) for v in groups.values()]
    if len({v.shape for v in values}) != 1:
        raise ValueError('Source-group shapes differ.')
    return {**groups, 'aggregate': np.sum(values,axis=0)}


def block_metrics(cpu, gpu) -> list[dict]:
    if len(cpu) != 6 or len(gpu) != 6:
        raise ValueError('The protocol requires exactly six paired seeds.')
    rows=[]
    for i,j in ((0,1),(2,3),(4,5)):
        a = (field_metrics(cpu[i],gpu[i])['L']+field_metrics(cpu[j],gpu[j])['L'])/2
        b = field_metrics(cpu[i],cpu[j])['L']
        d = field_metrics(gpu[i],gpu[j])['L']
        rows.append({'seed_indices':[i,j], 'A':a, 'B':b, 'D':d,
                     'R':None if a == b == 0 else ratio(a,b), 'V':None if d == b == 0 else ratio(d,b),
                     'ratio_status':'uninformative_zero' if b == 0 else 'informative',
                     'reference_zero':b==0,
                     'primary_pass':a == 0 if b == 0 else a/b < 1,
                     'dispersion_review':d != 0 if b == 0 else not .5 <= d/b <= 2})
    return rows


def bootstrap_blocks(blocks: list[dict]) -> dict:
    if len(blocks) != 3:
        raise ValueError('Exactly three independent blocks are required.')
    samples = list(itertools.product(range(3), repeat=3))
    output = {'resamples':len(samples),'coverage_established':False,
              'method':'exact enumeration; percentile; independent block unit; descriptive only'}
    for key,numerator in (('R','A'),('V','D')):
        values = [ratio(sum(blocks[i][numerator] for i in sample),sum(blocks[i]['B'] for i in sample)) if sum(blocks[i]['B'] for i in sample) or sum(blocks[i][numerator] for i in sample) else math.nan for sample in samples]
        finite = all(math.isfinite(v) for v in values)
        output[key] = {
            'estimate':ratio(sum(b[numerator] for b in blocks),sum(b['B'] for b in blocks)) if sum(b['B'] for b in blocks) or sum(b[numerator] for b in blocks) else None,
            'p2_5':float(np.quantile(values,.025)) if finite else None,
            'p97_5':float(np.quantile(values,.975)) if finite else None,
            'p95_upper':float(np.quantile(values,.95)) if finite else None,
            'undefined_resamples':sum(math.isnan(v) for v in values),
            'infinite_resamples':sum(math.isinf(v) for v in values),
            'all_cpu_references_zero':all(b['B']==0 for b in blocks),
        }
    return output


def summarize(values) -> dict:
    data = np.asarray(values,dtype=float)
    if data.ndim != 1 or data.size == 0 or not np.all(np.isfinite(data)):
        raise ValueError('Expected nonempty finite sample.')
    mean = float(data.mean())
    sd = float(data.std(ddof=1)) if data.size > 1 else None
    return {'n':int(data.size),'raw':data.tolist(),'mean':mean,'median':float(np.median(data)),
            'min':float(data.min()),'max':float(data.max()),'sample_sd':sd,
            'cv':ratio(sd,mean) if sd is not None else None}


def json_safe(value):
    """JSON has no infinity; keep its sign explicit rather than silently nulling it."""
    if isinstance(value,dict): return {str(k):json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [json_safe(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):
        return 'Infinity' if value > 0 else '-Infinity' if value < 0 else 'NaN'
    return value


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def load_fields(comp: Path, hours: int, grid=(50,50), groups=(1,2,3), slice_number=1):
    """Reuse the reviewed GRZ decoder, then restore the entire fixed zero-filled grid."""
    decoder_path = Path(__file__).resolve().parents[1] / 'validation' / 'compare.py'
    spec = importlib.util.spec_from_file_location('gral_validation_compare',decoder_path)
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    expected={f'{h:05d}.grz' for h in range(1,hours+1)}
    if {p.name for p in comp.glob('*.grz')} != expected:
        raise ValueError(f'Missing/extra GRZ hours: {comp}')
    result={str(g):np.zeros((hours,*grid)) for g in groups}
    for h in range(1,hours+1):
        with decoder.zipfile.ZipFile(comp/f'{h:05d}.grz') as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)):
                raise ValueError('Duplicate GRZ member.')
            for g in groups:
                name=f'{h:05d}-{slice_number}{g:02d}.con'
                if name not in names:
                    raise ValueError(f'Missing required member: {name}')
                payload=archive.read(name)
                mode=struct.unpack_from('<i',payload)[0]
                if mode==-3:
                    header=struct.unpack_from('<iiiffii',payload)
                    if header[1:]!=(2000,2000,20.,20.,*grid):raise ValueError('Dense grid georeferencing differs from fixture.')
                field=decoder.read_grid(payload)
                for (x,y),v in field.items():
                    if mode in (-1,-3):
                        # The shared decoder returns world-space cell centers for both formats.
                        if (x-2010)%20 or (y-2010)%20:raise ValueError('Sparse coordinate is not a fixture cell center.')
                        x,y=int((x-2010)//20+1),int((y-2010)//20+1)
                    if not (1 <= x <= grid[0] and 1 <= y <= grid[1]):
                        raise ValueError('Concentration coordinate outside fixed grid.')
                    result[str(g)][h-1,x-1,y-1]=v
    return aggregate_groups(result)


def scientific_summary(fields: dict) -> dict:
    """fields[(backend,offset)] contains source-group arrays for one science run."""
    required={(b,s) for b in ('cpu','gpu') for s in SEED_OFFSETS}
    if set(fields) != required:
        raise ValueError('Incomplete or extra scientific seed cohort.')
    group_names=set(fields[('cpu',0)])
    if any(set(v)!=group_names for v in fields.values()):
        raise ValueError('Scientific source groups differ.')
    output={'seed_count':6,'independent_block_count':3,'groups':{},
            'physical_validation_not_established':True,'formal_equivalence_not_tested':True,
            'inference_inconclusive':True}
    for group in sorted(group_names):
        cpu=[fields[('cpu',s)][group] for s in SEED_OFFSETS]
        gpu=[fields[('gpu',s)][group] for s in SEED_OFFSETS]
        if any(v.shape[0] != 24 for v in cpu+gpu):
            raise ValueError('Science cohort requires 24 hours.')
        c,g=[v[3:] for v in cpu],[v[3:] for v in gpu]
        blocks=block_metrics(c,g)
        pairs=[]
        for i,j in itertools.combinations(range(6),2):
            cm,gm=field_metrics(c[i],c[j]),field_metrics(g[i],g[j])
            pairs.append({'seed_indices':[i,j],'cpu':cm,'gpu':gm,'V':None if gm['L'] == cm['L'] == 0 else ratio(gm['L'],cm['L']), 'ratio_status':'uninformative_zero' if cm['L']==0 else 'informative'})
        output['groups'][group]={
            'primary_seed_metrics':[{'seed_offset':s,**field_metrics(a,b)} for s,a,b in zip(SEED_OFFSETS,c,g)],
            'all_hour_seed_metrics':[{'seed_offset':s,**field_metrics(a,b)} for s,a,b in zip(SEED_OFFSETS,cpu,gpu)],
            'blocks':blocks,'bootstrap':bootstrap_blocks(blocks),'interseed_pairs_dependent':pairs,
            'secondary_block_diagnostics':secondary_blocks(c,g),
            'dispersion_dependent_summary':dispersion_summary(pairs),
            'primary_gate_pass':all(b['primary_pass'] for b in blocks),
            'dispersion_review_required':any(b['dispersion_review'] for b in blocks),
            'secondary_review_status':'human_review_pending',
        }
    primary=all(v['primary_gate_pass'] for v in output['groups'].values())
    output['numeric_gate_status']='pass_observed_fixture' if primary else 'engineering_fail'
    output['decision']='engineering_review_required' if primary else 'engineering_fail'
    output['decision_reason']='Integrity evidence and secondary diagnostics require explicit review; numerical screening alone cannot certify the cohort.'
    return output


def dispersion_summary(pairs):
    values=[p['V'] for p in pairs if p['V'] is not None and math.isfinite(p['V'])]
    return {'dependent_pairs_not_replicates':True,'total_pairs':len(pairs),
            'uninformative_zero_pairs':sum(p['V'] is None for p in pairs),
            'infinite_pairs':sum(p['V'] is not None and not math.isfinite(p['V']) for p in pairs),
            'finite_summary':summarize(values) if values else None}


def secondary_blocks(cpu,gpu):
    output=[]
    for i,j in ((0,1),(2,3),(4,5)):
        a,b,ref=field_metrics(cpu[i],gpu[i]),field_metrics(cpu[j],gpu[j]),field_metrics(cpu[i],cpu[j])
        row={'seed_indices':[i,j]}
        for metric in ('normalized_bias','mean_difference'):
            row[metric]={'backend_absolute_mean':(abs(a[metric])+abs(b[metric]))/2,
                         'cpu_interseed_absolute':abs(ref[metric]),'backend_signed':[a[metric],b[metric]]}
        row['spatial_decorrelation']={'backend_mean':None if a['spatial_pearson'] is None or b['spatial_pearson'] is None else 1-(a['spatial_pearson']+b['spatial_pearson'])/2,
                                     'cpu_interseed':None if ref['spatial_pearson'] is None else 1-ref['spatial_pearson']}
        for metric in ('p95','p99'):
            row[metric]={'backend_absolute_mean':(a[metric]['absolute_difference']+b[metric]['absolute_difference'])/2,
                         'cpu_interseed_absolute':ref[metric]['absolute_difference'],
                         'backend_signed':[a[metric]['difference'],b[metric]['difference']]}
        output.append(row)
    return output


def read_csv(path: Path):
    if not path.exists(): return []
    with path.open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))




def gpu_device_intervals(rows: list[dict]) -> list[float | None]:
    """CUDA-event deltas between result snapshots; each run starts a new server."""
    previous = 0.0
    intervals = []
    for row in rows:
        cumulative = row.get('result_server_metrics', {}).get('kernel_device_ms')
        if cumulative is None:
            intervals.append(None)
            previous = None
            continue
        cumulative = float(cumulative)
        if not math.isfinite(cumulative) or cumulative < 0:
            raise ValueError('Invalid cumulative CUDA-event kernel time.')
        if previous is not None and cumulative < previous:
            raise ValueError('Cumulative CUDA-event kernel time decreased within one run.')
        intervals.append(None if previous is None else cumulative - previous)
        previous = cumulative
    return intervals


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()] if path.exists() else []


def observer_boundary_seconds(observer,hours):
    events=observer.get('raw_events',[])
    starts=[v for v in events if v.get('event_type')=='boundary' and v.get('boundary')=='start']
    stops=[v for v in events if v.get('event_type')=='boundary' and v.get('boundary')=='stop']
    finished=[v for v in events if v.get('event_type')=='finished']
    if len(starts)!=1 or len(stops)!=1 or len(finished)!=1:
        raise ValueError('Missing/duplicate observer boundary or finished event.')
    start,stop,finish=starts[0],stops[0],finished[0]
    if start['IWET']!=3 or stop['IWET']!=hours or stop['measured_situations']!=hours-3 or not finish['complete'] or finish['completed_situations']!=hours or finish['seeded_situations']!=hours:
        raise ValueError('Observer boundary/finished contract mismatch.')
    value=float(stop['elapsed_s'])-float(start['elapsed_s'])
    frequency=float(start['stopwatch_frequency'])
    if not math.isfinite(frequency) or frequency<=0:raise ValueError('Invalid stopwatch frequency.')
    computed=(stop['stopwatch_timestamp']-start['stopwatch_timestamp'])/frequency
    if frequency<=0 or not math.isfinite(value) or value<=0 or not math.isclose(value,computed,rel_tol=1e-5,abs_tol=1e-5):
        raise ValueError('Observer boundary duration is invalid or inconsistent.')
    return value


def validate_constant_inputs(comp: Path,hours: int):
    emissions=(comp/'emissions_timeseries.txt').read_text(encoding='ascii').splitlines()
    meteorology=(comp/'mettimeseries.dat').read_text(encoding='ascii').splitlines()
    if len(emissions)!=hours+2 or len(meteorology)!=hours+1:
        raise ValueError('Expected N real rows and one unused look-ahead row.')
    for index,(emission,met) in enumerate(zip(emissions[1:],meteorology)):
        e=emission.split(';');m=met.split()
        date=f'{1+index//24:02d}.01';hour=str(1+index%24)
        if len(e)!=5 or e[:2]!=[date,hour] or [float(v) for v in e[2:]]!=[1.,1.,1.]:
            raise ValueError('Actual source schedule is not the fixed constant input.')
        if len(m)!=5 or m[:2]!=[date,hour] or [float(v) for v in m[2:]]!=[2.,27.,4.]:
            raise ValueError('Actual meteorology is not the fixed constant input.')


def load_runs(study_path: Path):
    manifest=read_json(study_path)
    records=manifest['runs']
    if len(records)!=22 or len({r['run_id'] for r in records})!=22:
        raise ValueError('Expected 22 uniquely identified measured runs.')
    runs=[]
    for record in records:
        r=dict(record)
        if r['fixture_case']!='supported_primary' or r['backend'] not in ('cpu','gpu') or r['hours'] not in (24,48):
            raise ValueError('Unsupported measured cohort entry.')
        if r['role'] not in ('science','timing') or r['seed_offset'] not in SEED_OFFSETS:
            raise ValueError('Unknown role or seed offset.')
        root=Path(r['path'])
        if not root.is_absolute():root=study_path.parent/root
        result=read_json(root/'logs'/'result.json'); inputs=read_json(root/'input_manifest.json')
        if result['status']!='pass' or not result.get('timing_eligible'):
            raise ValueError(f'Failed/ineligible run: {r["run_id"]}')
        if (result['model_hours'],result['seed_offset'],result['requested_mode'])!=(r['hours'],r['seed_offset'],r['backend']):
            raise ValueError('Run result differs from study manifest.')
        if result['dispatch']['path'] != ('gpu' if r['backend']=='gpu' else 'cpu_requested'):
            raise ValueError('Measured cohort dispatch mismatch.')
        if inputs['grid_cells'] != [50,50] or inputs['workers']!=16 or inputs['particles_per_hour']!=360000:
            raise ValueError('Fixture differs from frozen grid/CPU/particle contract.')
        if inputs['hours']!=r['hours'] or len(inputs['factors'])!=r['hours'] or any(row!=[1,1,1] for row in inputs['factors']):
            raise ValueError('Expected constant unit source factors.')
        validate_constant_inputs(root/'Computation',r['hours'])
        for name,digest in inputs['input_sha256'].items():
            if sha256(root/name)!=digest:raise ValueError('Model input hash changed: '+name)
        observer=result.get('observer',{})
        series=observer.get('situation_series',[]);seeds=observer.get('seed_rows',[])
        if observer.get('status')!='pass' or [v['situation'] for v in series]!=list(range(1,r['hours']+1)) or [v['IWET'] for v in seeds]!=list(range(1,r['hours']+1)):
            raise ValueError('Observer or seed coverage is incomplete.')
        if any(v.get('time_scope')!='full_situation_after_stop_check' or v.get('seed_to_end_s') is None for v in series):raise ValueError('Full-situation observer scope is missing; old observer builds cannot be pooled.')
        if any(not math.isfinite(v['wall_s']) or v['wall_s']<=0 for v in series):
            raise ValueError('Invalid situation interval.')
        if any(not v.get('fixed_mode') for v in seeds):raise ValueError('Seed control is not fixed.')
        seed_states=[(v['Seed1'],v['Seed2']) for v in seeds]
        boundary_wall=observer_boundary_seconds(observer,r['hours'])
        r.update(root=root,result=result,inputs=inputs,series=series,seed_states=seed_states,
                 process_start_to_exit_s=result['process_start_to_exit_s'],
                 steady_wall_sum_s=sum(v['wall_s'] for v in series[3:]),
                 steady_boundary_wall_s=boundary_wall,
                 process_telemetry=read_csv(root/'logs'/'process_telemetry.csv'),
                 gpu_telemetry=read_csv(root/'logs'/'gpu_telemetry.csv'),
                 memory_detail=read_jsonl(root/'logs'/'process_memory.jsonl'),
                 gpu_metrics=read_jsonl(root/'logs'/'gpu_metrics.jsonl'))
        if not r['process_telemetry'] or any(not v.get('telemetry_samples') for v in series):raise ValueError('Process telemetry or within-situation samples are missing.')
        if not r['gpu_telemetry'] or any(v.get('query_error') for v in r['gpu_telemetry']) or not any(v.get('device_memory_used_mib') not in ('',None) for v in r['gpu_telemetry']):raise ValueError('Device-wide GPU telemetry is missing or failed.')
        if not r['memory_detail']:raise ValueError('Per-process memory telemetry is missing.')
        if r['backend']=='gpu' and [v['situation'] for v in r['gpu_metrics']]!=list(range(1,r['hours']+1)):raise ValueError('GPU pipeline metrics coverage is incomplete.')
        r['gpu_device_interval_ms']=gpu_device_intervals(r['gpu_metrics'])
        runs.append(r)
    science=[r for r in runs if r['role']=='science']
    if len(science)!=12 or {(r['backend'],r['seed_offset']) for r in science}!={(b,s) for b in ('cpu','gpu') for s in SEED_OFFSETS} or any(r['hours']!=24 for r in science):
        raise ValueError('Expected six complete 24h science pairs.')
    if any(r['inputs']['input_sha256']!=science[0]['inputs']['input_sha256'] for r in science):
        raise ValueError('Science cohort changes inputs beyond seed/backend.')
    by_pair={}
    for r in runs:
        key=r['pair_id'];by_pair.setdefault(key,[]).append(r)
    if len(by_pair)!=11 or any(len(v)!=2 or {r['backend'] for r in v}!={'cpu','gpu'} for v in by_pair.values()):
        raise ValueError('Expected eleven complete backend pairs.')
    for pair in by_pair.values():
        a,b=pair
        if a['hours']!=b['hours'] or a['seed_offset']!=b['seed_offset'] or a['seed_states']!=b['seed_states'] or a['inputs']['input_sha256']!=b['inputs']['input_sha256']:
            raise ValueError('CPU/GPU paired seed/input contract mismatch.')
    distinct={tuple(r['seed_states']) for r in science if r['backend']=='cpu'}
    if len(distinct)!=6:raise ValueError('Offsets did not produce six distinct seed sequences.')
    if any(r['result']['build_hashes']!=runs[0]['result']['build_hashes'] for r in runs):
        raise ValueError('Model build differs within cohort.')
    for h in (24,48):
        for b in ('cpu','gpu'):
            selected=[r for r in runs if r['seed_offset']==0 and r['hours']==h and r['backend']==b]
            if len(selected)!=3 or len({tuple(r['seed_states']) for r in selected})!=1:
                raise ValueError('Expected three fixed-seed timing repeats per duration/backend.')
    return manifest,runs


def timing_summary(runs):
    output={}
    for h in (24,48):
        selected=[r for r in runs if r['hours']==h and r['seed_offset']==0]
        info={}
        for key in ('process_start_to_exit_s','steady_boundary_wall_s','steady_wall_sum_s'):
            info[key]={b:summarize([r[key] for r in selected if r['backend']==b]) for b in ('cpu','gpu')}
            pairs={}
            for r in selected:pairs.setdefault(r['pair_id'],{})[r['backend']]=r[key]
            info[key]['paired_speedup']=summarize([p['cpu']/p['gpu'] for p in pairs.values()])
        output[str(h)]=info
    return output



def repeat_comparison(reference, candidate) -> dict:
    """Exact decoded arrays plus descriptive errors; no acceptance threshold."""
    values=field_metrics(reference,candidate)
    return {'symmetric_weighted_nmae':values['weighted_nmae'],
            'normalized_bias_candidate_minus_reference':values['normalized_bias'],
            'mean_difference_candidate_minus_reference':values['mean_difference'],
            'maximum_absolute_difference':values['max_absolute_difference'],
            'raw_array_equal':bool(np.array_equal(reference,candidate)),
            'different_values':int(np.count_nonzero(np.asarray(reference)!=np.asarray(candidate))),
            'compared_values':values['values'], 'zero_status':values['zero_status']}


def fixed_seed_repeatability(runs: list[dict], run_fields: dict) -> dict:
    """Dependent numerical repeats of base seed; never add to science seed n."""
    output={'scope':'supplementary descriptive comparison; primary gate unchanged',
            'added_during_measured_execution':True,
            'seed_offset':0,'independent_seed_count':1,
            'comparisons_are_dependent':True,'inferential_test':None,'acceptance_threshold':None,
            'raw_array_equal_definition':'exact equality of decoded full-grid arrays, not archive byte equality',
            'durations':{}}
    for hours in (24,48):
        selected=[r for r in runs if r['hours']==hours and r['seed_offset']==0]
        backend={name:sorted((r for r in selected if r['backend']==name),key=lambda r:(r['repeat'],r['run_id'])) for name in ('cpu','gpu')}
        if any(len(v)!=3 for v in backend.values()):
            raise ValueError('Numerical repeatability requires three base-seed repeats per backend.')
        pairs={r['pair_id']:r for r in backend['gpu']}
        if len(pairs)!=3 or {r['pair_id'] for r in backend['cpu']}!=set(pairs):
            raise ValueError('Fixed-seed numerical repeat pairs are incomplete.')
        for r in selected:
            if r['run_id'] not in run_fields:raise ValueError('Missing fixed-seed decoded field.')
            if any(v.shape[0]!=hours for v in run_fields[r['run_id']].values()):
                raise ValueError('Fixed-seed repeat duration mismatch.')
        group_names=set(run_fields[selected[0]['run_id']])
        if any(set(run_fields[r['run_id']])!=group_names for r in selected):
            raise ValueError('Fixed-seed repeat source-group mismatch.')
        duration={'backend_pairs':3,'self_pairs_per_backend':3,'windows':{}}
        for window,start in (('all_hours',0),('hours_4_to_end',3)):
            groups={}
            for group in sorted(group_names):
                def compare_runs(a,b):
                    return {'reference_run_id':a['run_id'],'candidate_run_id':b['run_id'],
                            'reference_backend':a['backend'],'candidate_backend':b['backend'],
                            **repeat_comparison(run_fields[a['run_id']][group][start:],run_fields[b['run_id']][group][start:])}
                groups[group]={
                    'paired_cpu_gpu':[compare_runs(r,pairs[r['pair_id']]) for r in backend['cpu']],
                    'cpu_self_pairs':[compare_runs(a,b) for a,b in itertools.combinations(backend['cpu'],2)],
                    'gpu_self_pairs':[compare_runs(a,b) for a,b in itertools.combinations(backend['gpu'],2)]}
            duration['windows'][window]={'first_hour':start+1,'last_hour':hours,'groups':groups}
        output['durations'][str(hours)]=duration
    return output


def analyze(study_path: Path,out: Path):
    out.mkdir(parents=True,exist_ok=False)
    try:
        manifest,runs=load_runs(study_path)
        fields={(r['backend'],r['seed_offset']):load_fields(r['root']/'Computation',24) for r in runs if r['role']=='science'}
        scientific=scientific_summary(fields)
        repeated_fields={}
        for r in runs:
            if r['seed_offset']==0:
                repeated_fields[r['run_id']]=fields[(r['backend'],0)] if r['role']=='science' else load_fields(r['root']/'Computation',r['hours'])
        repeatability=fixed_seed_repeatability(runs,repeated_fields)
        protocol=Path(__file__).resolve().parents[1]/'qa'/'statistical_protocol.json'
        summary={'status':'analyzed_pending_review','study_sha256':sha256(study_path),
                 'protocol_sha256':sha256(protocol),
                 'analysis_metadata':{'independence_of_rng_streams_verified':False,
                     'seed_pair_blocks':'three disjoint prespecified seed-pair blocks: (0,1), (2,3), (4,5)',
                     'legacy_independent_block_count':'design block count only; RNG stream independence has not been verified',
                     'bootstrap_scope':'descriptive resampling of disjoint blocks; no established coverage guarantee'},
                 'analysis_source_sha256':{p.name:sha256(p) for p in Path(__file__).parent.glob('*.py')},'scientific':scientific,'timing':timing_summary(runs),'fixed_seed_numerical_repeatability':repeatability,
                 'measurement_scope':{'situation_time':'Full situation start after stop check to CompleteSituation; includes field/setup work; final output drain is outside interval',
                     'seed_to_end':'Additional diagnostic interval from RecordSeed to CompleteSituation',
                     'steady_sum':'sum of full situation intervals 4..N; not process end-to-end or boundary wall time',
                     'steady_boundary':'observer boundary start after situation3/drain through end/drain; includes intervening setup gaps',
                     'gpu_memory':'device-wide used memory; not process VRAM','device_buffers':'application allocation counters',
                     'device_kernel_time':'per-situation difference of cumulative result_server_metrics.kernel_device_ms; CUDA events',
                     'legacy_kernel_named_host_timers':'fresh_kernel_ms, residual_kernel_ms, and kernel_total_ms include host launch, synchronization, and status-read time; nested in host roundtrips'},
                 'run_measurements':[]}
        for r in runs:
            sample_times=[float(row['elapsed_s']) for row in r['process_telemetry']]
            memory={}
            for key in ('tree_rss_bytes','tree_private_bytes','dotnet_rss_bytes','python_rss_bytes','os_peak_working_set_bytes'):
                values=[float(v[key]) for v in r['process_telemetry'] if v.get(key) not in ('',None)]
                memory[key+'_observed_max']=max(values) if values else None
            gpu=[float(v['device_memory_used_mib']) for v in r['gpu_telemetry'] if v.get('device_memory_used_mib') not in ('',None) and not v.get('query_error')]
            memory['device_wide_gpu_mib_max']=max(gpu) if gpu else None
            memory['device_wide_gpu_mib_first_sample']=gpu[0] if gpu else None
            summary['run_measurements'].append({k:r[k] for k in ('run_id','backend','hours','seed_offset','pair_id','role','process_start_to_exit_s','steady_boundary_wall_s','steady_wall_sum_s')} |
                {'memory':memory,'sample_interval_s':summarize(np.diff(sample_times)) if len(sample_times)>1 else None,
                 'situations_without_memory_samples':[s['situation'] for s in r['series'] if not s.get('telemetry_samples')],
                 'situation_series':r['series'],'gpu_telemetry_missing':not bool(gpu),
                 'input_manifest_sha256':sha256(r['root']/'input_manifest.json'),'result_sha256':sha256(r['root']/'logs'/'result.json')})
        phase_rows=[]
        from plot_study import PHASES,render_all
        for r in runs:
            for row,device_ms in zip(r['gpu_metrics'],r['gpu_device_interval_ms']):
                phase_rows.append({'run_id':r['run_id'],'hours':r['hours'],'seed_offset':r['seed_offset'],
                    **{k:row.get(k) for k in ['situation',*PHASES,'cache_hash_s','fresh_kernel_ms','residual_kernel_ms','kernel_total_ms','saved_payload_bytes','bytes_sent','bytes_received']},
                    'phase_sum_s':sum(row[k] for k in PHASES),
                    'kernel_is_nested':True,
                    'kernel_device_interval_ms':device_ms,
                    'kernel_device_cumulative_ms':row.get('result_server_metrics',{}).get('kernel_device_ms'),
                    'host_launch_sync_status_interval_ms':row['fresh_kernel_ms']+row['residual_kernel_ms'] if row.get('fresh_kernel_ms') is not None and row.get('residual_kernel_ms') is not None else None,
                    'legacy_kernel_named_timer_scope':'host launch + synchronization + status read; not pure CUDA-event duration',
                    **row.get('result_server_metrics',{})})
        (out/'numerical_repeatability.json').write_text(json.dumps(json_safe(repeatability),indent=2,allow_nan=False),encoding='utf-8')
        (out/'gpu_pipeline_phases.json').write_text(json.dumps(json_safe(phase_rows),indent=2,allow_nan=False),encoding='utf-8')
        render_all(runs,fields,scientific,out/'figures')
        (out/'analysis_summary.json').write_text(json.dumps(json_safe(summary),indent=2,allow_nan=False),encoding='utf-8')
        artifacts={str(p.relative_to(out)):sha256(p) for p in sorted(out.rglob('*')) if p.is_file()}
        (out/'artifact_sha256.json').write_text(json.dumps(artifacts,indent=2),encoding='utf-8')
        print('[ANALYSIS]',summary['status'],scientific['numeric_gate_status'])
        return summary
    except (KeyError,ValueError,OSError) as exc:
        (out/'invalid_analysis.json').write_text(json.dumps({'status':'INVALID','error':str(exc)},indent=2),encoding='utf-8')
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True,help='Study manifest JSON; schema supplied by validation harness.')
    parser.add_argument('--out',type=Path,required=True,help='New output directory; must not already exist.')
    args=parser.parse_args()
    analyze(args.study,args.out)


if __name__=='__main__':
    main()
