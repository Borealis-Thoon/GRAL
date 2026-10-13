"""Aggregate completed follow-up trials; never launch builds or model processes.

Only measured pass/pass rows enter timing and fidelity comparisons. Positive
paired_change_pct means a larger value (slower or more memory). Measured-repeat
fidelity compares every measured pair, never the discarded warm-up.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import struct
import zipfile

VARIANTS = ('double', 'dictionary_fixed', 'output_index', 'static_update', 'combined')
METRICS = ('wall_s', 'cpu_s', 'peak_commit_mib', 'peak_working_mib')
MIB = 1024**2


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def write_csv(path, rows):
    columns=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v, ensure_ascii=False) if isinstance(v, (list,dict)) else v for k,v in row.items()})


def descriptive(values):
    values=[x for x in values if x is not None]
    return {'n':len(values), 'median':statistics.median(values) if values else None,
            'min':min(values) if values else None, 'max':max(values) if values else None}


def metric(row, name):
    if name in ('wall_s', 'cpu_s'):
        value=row.get(name)
    else:
        key={'peak_commit_mib':'PeakPagefileUsage', 'peak_working_mib':'PeakWorkingSetSize'}[name]
        value=row.get('memory',{}).get(key)
        if value is not None: value/=MIB
    if value is not None and (not math.isfinite(value) or value < 0):
        raise ValueError((name,value))
    return value


def key(row):
    return row['tag'],row['case'],row['variant'],row['repeat']


def read_inputs(job, selected_tags):
    results=job/'results'; rows=[]; comparisons=[]; origins=[]; conditions={}; plans={}; skipped=[]; warnings=[]
    folders=sorted(p for p in results.iterdir() if p.is_dir() and (not selected_tags or p.name in selected_tags))
    if selected_tags:
        missing=set(selected_tags)-{p.name for p in folders}
        if missing: raise ValueError('Missing selected tags: '+str(sorted(missing)))
    for folder in folders:
        completion=folder/'completion.json'
        if not completion.exists() or not load(completion).get('completed'):
            if selected_tags: raise ValueError('Selected tag is incomplete: '+folder.name)
            skipped.append(folder.name); continue
        completed=load(completion); plan=load(folder/'plan.json'); plans[folder.name]=plan
        trial_rows=load(folder/'records.json')
        if len(trial_rows)!=completed['runs']: raise ValueError('Completion row count mismatch: '+folder.name)
        rows.extend(dict(r,tag=folder.name) for r in trial_rows)
        comparisons.extend(dict(c,tag=folder.name) for c in load(folder/'comparisons.json'))
        for c in load(folder/'conditions.json'): conditions[folder.name,c['id']]=c
        for filename in ('records.json','comparisons.json','conditions.json','plan.json','completion.json'):
            path=folder/filename
            origins.append({'path':str(path.relative_to(job)), 'sha256':sha(path), 'bytes':path.stat().st_size})
        for c in plan['cases']:
            for variant in plan['variants']:
                actual=sorted(r['repeat'] for r in trial_rows if r['case']==c['id'] and r['variant']==variant)
                expected=list(range(plan['measured_repeats']+1))
                if actual!=expected: warnings.append({'tag':folder.name,'case':c['id'],'variant':variant,'expected_repeats':expected,'actual_repeats':actual})
    keys=[key(r) for r in rows]
    if len(keys)!=len(set(keys)): raise ValueError('Duplicate tag/case/variant/repeat keys')
    unknown=set(r['variant'] for r in rows)-set(VARIANTS)
    if unknown: warnings.append({'unknown_variants':sorted(unknown)})
    return rows, comparisons, origins, conditions, plans, skipped, warnings


class PayloadReader:
    def __init__(self, job, row):
        self.folder=job/'results'/row['tag']/'runs'/f"{row['case']}_{row['variant']}_{row['repeat']}"
        self.hashes=row['payload_hashes']; self.zips={}; self.cache={}
    def values(self, field):
        if field not in self.cache:
            import numpy as np
            archive,entry=field.split(':',1)
            if archive not in self.zips: self.zips[archive]=zipfile.ZipFile(self.folder/archive)
            payload=self.zips[archive].read(entry)
            if hashlib.sha256(payload).hexdigest()!=self.hashes[field]: raise ValueError('Payload differs from record: '+str(self.folder/field))
            header,x,y,dx,dy,nx,ny=struct.unpack_from('<iiiffii',payload)
            if header!=-3 or len(payload)!=28+nx*ny*4: raise ValueError('Unexpected V03 payload')
            values=np.frombuffer(payload[28:],dtype='<f4').astype(np.float64)
            if not np.isfinite(values).all() or (values<0).any(): raise ValueError('Invalid decoded values')
            self.cache[field]=values
        return self.cache[field]
    def close(self):
        for stream in self.zips.values(): stream.close()
        self.cache.clear()


def fidelity(job, reference, variant, condition):
    """Compare concentration and deposition separately, then jointly.

    Equal saved payload hashes avoid re-reading large identical grids. Differing
    payloads are re-hashed and decoded. The concentration denominator comes from
    the validated saved situation sums; deposition is summed when needed.
    """
    hashes_a=reference['payload_hashes']; hashes_b=variant['payload_hashes']
    fields_a=set(hashes_a); fields_b=set(hashes_b)
    if fields_a!=fields_b:
        return [{'scope':'all','comparable':False,'missing_fields':sorted(fields_a-fields_b),'extra_fields':sorted(fields_b-fields_a)}]
    if not fields_a: return [{'scope':'all','comparable':False,'reason':'no output fields'}]
    readers=PayloadReader(job,reference),PayloadReader(job,variant)
    nxny=condition['nx']*condition['ny']; out=[]
    try:
        for scope in ('con','dep'):
            fields=sorted(k for k in fields_a if k.endswith('.'+scope))
            if not fields: continue
            row={'scope':scope,'comparable':True,'fields':len(fields),'values':len(fields)*nxny,
                 'payload_exact_fields':0,'numeric_exact_fields':0,'changed_values':0,'sum_abs':0.0,'max_abs':0.0}
            for field in fields:
                if hashes_a[field]==hashes_b[field]:
                    row['payload_exact_fields']+=1; row['numeric_exact_fields']+=1; continue
                import numpy as np
                a,b=readers[0].values(field),readers[1].values(field)
                if a.size!=nxny or b.size!=nxny: raise ValueError('Grid value count mismatch')
                delta=np.abs(a-b); changed=int(np.count_nonzero(a!=b))
                row['changed_values']+=changed; row['sum_abs']+=float(delta.sum())
                row['max_abs']=max(row['max_abs'],float(delta.max(initial=0)))
                if changed==0: row['numeric_exact_fields']+=1
            row['exact']=row['changed_values']==0
            if scope=='con': row['reference_sum']=sum(reference['situation_sums'].values())
            elif not row['exact']: row['reference_sum']=sum(float(readers[0].values(k).sum()) for k in fields)
            else: row['reference_sum']=None
            denom=row['reference_sum']
            row['relative_l1']=0.0 if row['exact'] else row['sum_abs']/denom if denom else None
            if not row['exact'] and not denom: row['zero_reference_nonzero_difference']=True
            out.append(row)
        if not out: return [{'scope':'all','comparable':False,'reason':'no con or dep fields'}]
        whole={'scope':'all','comparable':True}
        for k in ('fields','values','payload_exact_fields','numeric_exact_fields','changed_values','sum_abs'):
            whole[k]=sum(r[k] for r in out)
        whole['max_abs']=max(r['max_abs'] for r in out); whole['exact']=whole['changed_values']==0
        if not whole['exact']:
            for r in out:
                if r['reference_sum'] is None:
                    r['reference_sum']=sum(float(readers[0].values(k).sum()) for k in fields_a if k.endswith('.'+r['scope']))
            whole['reference_sum']=sum(r['reference_sum'] for r in out)
            whole['relative_l1']=whole['sum_abs']/whole['reference_sum'] if whole['reference_sum'] else None
        else:
            whole['reference_sum']=sum(r['reference_sum'] for r in out) if all(r['reference_sum'] is not None for r in out) else None
            whole['relative_l1']=0.0
        out.append(whole)
        return out
    finally:
        for reader in readers: reader.close()


def performance(rows, conditions):
    valid=[r for r in rows if r.get('measured') and r.get('status')=='pass']
    groups=defaultdict(list)
    for row in valid: groups[row['tag'],row['case'],row['variant']].append(row)
    medians=[]
    for (tag,case,variant), items in sorted(groups.items()):
        out={'tag':tag,'case':case,'variant':variant,'n':len(items),'repeats':sorted(r['repeat'] for r in items),
             'condition':conditions[tag,case]}
        for name in METRICS:
            out.update({name+'_'+k:v for k,v in descriptive([metric(r,name) for r in items]).items()})
        medians.append(out)
    bycase=defaultdict(dict)
    for row in valid: bycase[row['tag'],row['case'],row['repeat']][row['variant']]=row
    pairs=[]
    for (tag,case,repeat), variants in sorted(bycase.items()):
        available=[v for v in VARIANTS if v in variants]
        for reference,variant in itertools.combinations(available,2):
            a,b=variants[reference],variants[variant]
            out={'tag':tag,'case':case,'repeat':repeat,'reference':reference,'variant':variant}
            for name in METRICS:
                x,y=metric(a,name),metric(b,name)
                out[name+'_reference']=x;out[name+'_variant']=y
                out[name+'_delta']=y-x if x is not None and y is not None else None
                out[name+'_change_pct']=100*(y/x-1) if x and y is not None else None
            pairs.append(out)
    grouped=defaultdict(list)
    for row in pairs: grouped[row['tag'],row['case'],row['reference'],row['variant']].append(row)
    paired=[]
    for (tag,case,reference,variant), items in sorted(grouped.items()):
        out={'tag':tag,'case':case,'reference':reference,'variant':variant,'n':len(items),
             'faster_count':sum(r['wall_s_change_pct']<0 for r in items if r['wall_s_change_pct'] is not None)}
        for name in METRICS:
            for kind in ('change_pct','delta'):
                out.update({name+'_'+kind+'_'+k:v for k,v in descriptive([r[name+'_'+kind] for r in items]).items()})
        paired.append(out)
    return valid,medians,pairs,paired


def fidelity_summary(rows):
    groups=defaultdict(list)
    for row in rows:
        groups[row['tag'],row['case'],row['kind'],row['reference'],row['variant'],row['scope']].append(row)
    out=[]
    for (tag,case,kind,reference,variant,scope), items in sorted(groups.items()):
        comparable=[r for r in items if r.get('comparable')]
        out.append({'tag':tag,'case':case,'kind':kind,'reference':reference,'variant':variant,'scope':scope,
                    'comparisons':len(items),'comparable':len(comparable),'exact_comparisons':sum(r['exact'] for r in comparable),
                    'fields_compared_sum':sum(r['fields'] for r in comparable),'values_compared_sum':sum(r['values'] for r in comparable),
                    'payload_exact_fields_sum':sum(r['payload_exact_fields'] for r in comparable),
                    'numeric_exact_fields_sum':sum(r['numeric_exact_fields'] for r in comparable),
                    'changed_values_max':max((r['changed_values'] for r in comparable),default=None),
                    'relative_l1_max':max((r['relative_l1'] for r in comparable if r['relative_l1'] is not None),default=None),
                    'max_abs_max':max((r['max_abs'] for r in comparable),default=None)})
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--tags',nargs='+')
    args=parser.parse_args(); job=args.job.resolve()
    rows,stored,origins,conditions,plans,skipped,warnings=read_inputs(job,args.tags)
    if not rows: raise ValueError('No completed records found')
    valid,medians,pairs,paired=performance(rows,conditions)
    bykey={key(r):r for r in valid}; numerical=[]
    stored_map={(r['tag'],r['case'],r['reference'],r['variant'],r['repeat']):r for r in stored if r.get('kind')=='paired'}
    crosschecks=[]
    for r in valid:
        if r['variant']=='double': continue
        baseline=bykey.get((r['tag'],r['case'],'double',r['repeat']))
        if baseline is None: continue
        diff=fidelity(job,baseline,r,conditions[r['tag'],r['case']])
        for item in diff:
            numerical.append(dict(tag=r['tag'],case=r['case'],kind='paired',reference='double',variant=r['variant'],reference_repeat=r['repeat'],repeat=r['repeat'],**item))
        old=stored_map.get((r['tag'],r['case'],'double',r['variant'],r['repeat']))
        if old:
            new=next(x for x in diff if x['scope']=='all'); issues=[]
            for name in ('comparable','fields','values','changed_values','exact'):
                if old.get(name)!=new.get(name): issues.append(name)
            for name in ('relative_l1','max_abs'):
                a,b=old.get(name),new.get(name)
                if a is None or b is None:
                    if a!=b: issues.append(name)
                elif not math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-30): issues.append(name)
            crosschecks.append({'tag':r['tag'],'case':r['case'],'variant':r['variant'],'repeat':r['repeat'],'passed':not issues,'differences':issues})
            if issues: raise ValueError('Stored comparison disagrees with recomputation: '+str(crosschecks[-1]))
    repeat_groups=defaultdict(list)
    for r in valid: repeat_groups[r['tag'],r['case'],r['variant']].append(r)
    for (tag,case,variant), items in sorted(repeat_groups.items()):
        for a,b in itertools.combinations(sorted(items,key=lambda r:r['repeat']),2):
            for item in fidelity(job,a,b,conditions[tag,case]):
                numerical.append(dict(tag=tag,case=case,kind='measured_repeat_pair',reference=variant,variant=variant,reference_repeat=a['repeat'],repeat=b['repeat'],**item))
    excluded=[{k:r.get(k) for k in ('tag','case','variant','repeat','measured','status','issues','error')} for r in rows if r.get('status')!='pass']
    summary={'method':{'performance':'Measured status=pass only; pair within identical tag/case/repeat; one warm-up excluded. No pooling across tags.',
                       'paired_percentage':'100 * (variant / reference - 1); positive means slower or greater memory/CPU use. Median and full observed range reported.',
                       'numerical':'Measured pass/pass; double-paired comparison plus every measured repeat pair. con and dep are separate. All uses both types.',
                       'payload_equality':'Equal saved SHA256 payload hashes are accepted as byte equality; differing payloads are re-hashed and decoded as float32.',
                       'repeat_denominator':'Earlier measured repeat is the reference; warm-up is never a repeat reference.',
                       'cpu':'Kernel plus user process CPU seconds from GetProcessTimes.',
                       'memory':'PeakPagefileUsage process commit and PeakWorkingSetSize divided by 2^20.',
                       'uncertainty':'Descriptive medians and full observed ranges; no confidence interval or significance claim.'},
             'counts':{'completed_tags':len(plans),'records_all':len(rows),'warmup_records':sum(not r.get('measured') for r in rows),'measured_records':sum(bool(r.get('measured')) for r in rows),
                       'measured_pass_records':len(valid),'nonpass_records':len(excluded),'paired_performance_rows':len(pairs),'paired_numerical_all_scope':sum(r['kind']=='paired' and r['scope']=='all' for r in numerical),
                       'measured_repeat_all_scope':sum(r['kind']=='measured_repeat_pair' and r['scope']=='all' for r in numerical),'status_counts':dict(Counter(r.get('status') for r in rows))},
             'script_sha256':sha(Path(__file__)),'source_files':origins,'selected_tags':sorted(plans),'skipped_incomplete_tags':skipped,'input_warnings':warnings,
             'variant_summaries':medians,'paired_performance':paired,'numerical_summary':fidelity_summary(numerical),'excluded_nonpass':excluded,'stored_comparison_crosschecks':crosschecks}
    out=job/'results'
    dump(out/'followup_analysis.json',summary)
    write_csv(out/'followup_variant_summary.csv',medians)
    write_csv(out/'followup_paired_raw.csv',pairs)
    write_csv(out/'followup_paired_summary.csv',paired)
    write_csv(out/'followup_numerical_raw.csv',numerical)
    write_csv(out/'followup_numerical_summary.csv',summary['numerical_summary'])
    write_csv(out/'followup_excluded.csv',excluded)
    print('[DONE]',json.dumps(summary['counts'],ensure_ascii=True))


if __name__=='__main__':
    main()
