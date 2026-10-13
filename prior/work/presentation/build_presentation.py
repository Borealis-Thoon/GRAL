"""Build descriptive paired summaries and figures from finished PR64 experiments.
No engine runs. Use measured pass/pass pairs only for performance.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics as st

VARIANTS = ('float', 'double', 'dictionary', 'dictionary_fixed')
LABELS = {'float':'Current float', 'double':'PR #64 double',
          'dictionary':'Developer dictionary', 'dictionary_fixed':'Dictionary + regression fixes'}
COLORS = {'float':'#526574','double':'#B57919','dictionary':'#9B65A7','dictionary_fixed':'#087E8B'}
MARKERS = {'float':'o','double':'^','dictionary':'s','dictionary_fixed':'o'}
MIB = 1024**2

def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def csv_write(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v, ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})

def median(xs):
    return st.median(xs) if xs else None

def changes(a,b):
    return 100.0*(1.0-a/b) if b else None

def value(record,key):
    if key=='wall_s': return record['wall_s']
    if key=='cpu_s': return record.get('cpu_s')
    return record.get('memory',{}).get(key,0)/MIB

def read_all(root, tags):
    records=[]; comparisons=[]; conditions={}; origins=[]; skipped=[]
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or (tags and folder.name not in tags): continue
        completion=folder/'completion.json'
        if not completion.exists() or not load(completion).get('completed'):
            skipped.append(folder.name); continue
        for name, target in [('records.json',records),('comparisons.json',comparisons)]:
            path=folder/name
            if path.exists():
                target.extend(dict(x,tag=folder.name) for x in load(path))
        cp=folder/'conditions.json'
        items=load(cp) if cp.exists() else load(folder/'plan.json')['cases']
        for c in items: conditions[(folder.name,c['id'])]=c
        for name in ('records.json','comparisons.json','conditions.json','plan.json','completion.json'):
            path=folder/name
            if path.exists(): origins.append({'path':f'{folder.name}/{name}','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    keys=[(r['tag'],r['case'],r['variant'],r['repeat']) for r in records]
    if len(set(keys))!=len(keys): raise ValueError('Duplicate tag/case/variant/repeat keys')
    return records,comparisons,conditions,origins,skipped

def summarize(records, comparisons, conditions):
    bykey={(r['tag'],r['case'],r['variant'],r['repeat']):r for r in records}
    groups=defaultdict(list)
    for r in records:
        if r.get('measured') and r.get('status')=='pass': groups[(r['tag'],r['case'],r['variant'])].append(r)
    medians=[]
    for (tag,case,variant), rs in sorted(groups.items()):
        c=conditions[(tag,case)]
        row={'tag':tag,'case':case,'variant':variant,'n':len(rs),
             'wall_s_median':median([r['wall_s'] for r in rs]),'wall_s_min':min(r['wall_s'] for r in rs),'wall_s_max':max(r['wall_s'] for r in rs),
             'peak_commit_mib_median':median([value(r,'PeakPagefileUsage') for r in rs]),
             'peak_working_mib_median':median([value(r,'PeakWorkingSetSize') for r in rs]),
             'output_nonzero_fraction_median':median([r['occupied_fraction'] for r in rs if r.get('occupied_fraction') is not None]),
             'condition':c}
        medians.append(row)
    pairs=[]
    for r in records:
        if not r.get('measured') or r.get('status')!='pass': continue
        for baseline in ('float','double'):
            if r['variant']==baseline: continue
            base=bykey.get((r['tag'],r['case'],baseline,r['repeat']))
            if not base or not base.get('measured') or base.get('status')!='pass': continue
            row={k:r[k] for k in ('tag','case','variant','repeat')}; row['reference']=baseline
            for key,name in [('wall_s','runtime'),('PeakPagefileUsage','peak_commit'),('PeakWorkingSetSize','peak_working')]:
                a,b=value(r,key),value(base,key)
                row[name+'_reduction_pct']=changes(a,b)
                row[name+'_delta' + ('_s' if key=='wall_s' else '_mib')]=a-b
                row[name+'_reference']=b; row[name+'_variant']=a
            pairs.append(row)
    paired_groups=defaultdict(list)
    for row in pairs: paired_groups[(row['tag'],row['case'],row['reference'],row['variant'])].append(row)
    paired=[]
    for (tag,case,reference,variant), rows in sorted(paired_groups.items()):
        out={'tag':tag,'case':case,'reference':reference,'variant':variant,'n':len(rows),'faster_count':sum(r['runtime_reduction_pct']>0 for r in rows)}
        for name in ('runtime','peak_commit','peak_working'):
            xs=[r[name+'_reduction_pct'] for r in rows]
            out[name+'_reduction_pct_median']=median(xs)
            out[name+'_reduction_pct_min']=min(xs)
            out[name+'_reduction_pct_max']=max(xs)
            unit='_s' if name=='runtime' else '_mib'
            out[name+'_delta'+unit+'_median']=median([r[name+'_delta'+unit] for r in rows])
        paired.append(out)
    fidelity=[]
    for c in comparisons:
        if c.get('kind')!='paired': continue
        a=bykey.get((c['tag'],c['case'],c['variant'],c['repeat']))
        b=bykey.get((c['tag'],c['case'],c['reference'],c['repeat']))
        fidelity.append(dict(c,measured=bool(a and b and a.get('measured') and b.get('measured')),
                             variant_status=a.get('status') if a else None,reference_status=b.get('status') if b else None))
    excluded=[{k:r.get(k) for k in ('tag','case','variant','repeat','measured','status','issues')} for r in records if r.get('status')!='pass']
    return medians,pairs,paired,fidelity,excluded

def label(case,c):
    names={'small_sg1_t1':'Small / 1 group','dense_sg1_coarse_t4':'Dense plume / 1 group',
           'sparse_sg99_fine9_t4':'Fine grid / 99 groups / 9 slices',
           'terrain_stable_area_t8':'Stable terrain / area sources',
           'convective_mixed_t8':'Convective / mixed sources',
           'transient_three_t1':'Three transient weather steps', 'transient_three_t4':'Three transient weather steps',
           'buildings_mixed_t4':'Buildings / mixed sources', 'hot_stack_t1':'Buoyant point sources',
           'high_pps_t8':'8,000 particles/s', 'medium_8000ps_t8':'128 sources / 8,000 particles/s'}
    stem=names.get(case,case.replace('_',' '))
    if case.startswith('neutral_sg26_t'): stem='Neutral / 26 groups'
    return f"{stem} | {c.get('workers','?')} workers"

def style(plt):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                        'axes.spines.right':False,'axes.titleweight':'bold','svg.fonttype':'none',
                        'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white'})

def save(fig,path,source):
    fig.savefig(path.with_suffix('.png'),dpi=180,bbox_inches='tight')
    fig.savefig(path.with_suffix('.svg'),bbox_inches='tight')
    dump(path.with_suffix('.json'),source)

def plots(out,records,medians,pairs,paired,conditions,origins):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    style(plt)
    # Main comparator is PR64 double on the same current baseline.
    allkeys={(p['tag'],p['case']) for p in paired if p['reference']=='double' and p['variant']=='dictionary_fixed'}
    representatives=[('sparse_final','sparse_sg99_fine9_t4'),('scaling','neutral_sg26_t4'),('scaling','neutral_sg26_t14'),('workloads','terrain_stable_area_t8'),('load_transient','medium_8000ps_t8'),('workloads','dense_sg1_coarse_t4')]
    keys=[k for k in representatives if k in allkeys]
    if not keys: keys=sorted(allkeys)
    if keys:
        fig,axs=plt.subplots(1,2,figsize=(15,max(6.4,0.67*len(keys)+2.6)),sharey=True)
        medmap={(r['tag'],r['case'],r['variant']):r for r in medians}
        for i,key in enumerate(keys):
            tag,case=key
            for j,v in enumerate(('float','double','dictionary')):
                rows=[p for p in pairs if (p['tag'],p['case'])==key and p['reference']=='double' and p['variant']==v]
                y=i+(j-1)*0.20
                med=medmap.get((tag,case,v))
                if not med: continue
                face='white' if v=='dictionary_fixed' else COLORS[v]
                # Original and corrected dictionary stay separately labelled.
                xs=[-r['runtime_reduction_pct'] for r in rows] if v!='double' else [0.0]
                if xs:
                    axs[0].scatter(xs,[y]*len(xs),s=13,color=COLORS[v],alpha=.25,zorder=2)
                    axs[0].scatter([median(xs)],[y],s=48,marker=MARKERS[v],facecolors=face,edgecolors=COLORS[v],linewidth=1.35,zorder=3)
                raw=[r for r in records if (r['tag'],r['case'],r['variant'])==(tag,case,v) and r.get('measured') and r.get('status')=='pass']
                ms=[value(r,'PeakPagefileUsage') for r in raw]
                axs[1].scatter(ms,[y]*len(ms),s=13,color=COLORS[v],alpha=.25,zorder=2)
                axs[1].scatter([med['peak_commit_mib_median']],[y],s=48,marker=MARKERS[v],facecolors=face,edgecolors=COLORS[v],linewidth=1.35,zorder=3)
            for ax in axs:
                if i%2==0: ax.axhspan(i-.45,i+.45,color='#EFF3F5',zorder=0)
        axs[0].set_yticks(range(len(keys)),[label(case,conditions[(tag,case)]) for tag,case in keys])
        axs[0].invert_yaxis()
        axs[0].axvline(0,color='#61717D',lw=1,zorder=1)
        axs[0].set_xlabel('Runtime change from PR #64 double (%)\nLeft = faster; right = slower')
        axs[0].set_title('Whole-process time | paired comparisons',pad=14,fontsize=11)
        axs[1].set_xlabel('Peak process commit (MiB; log scale)\nLeft = less memory')
        axs[1].set_title('Peak process commit | original vs arrays',pad=14,fontsize=11)
        axs[1].set_xscale('log')
        axs[1].set_xticks([40,80,160,320,640],['40','80','160','320','640'])
        axs[1].xaxis.set_minor_formatter(plt.NullFormatter())
        for ax in axs: ax.grid(axis='x',alpha=.2)
        handles=[Line2D([0],[0],color=COLORS[v],marker=MARKERS[v],markerfacecolor='white' if v=='dictionary_fixed' else COLORS[v],ls='',label=LABELS[v]) for v in ('float','double','dictionary')]
        fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.61,.004),ncol=3,frameon=False)
        fig.suptitle('A large sparse output saves memory, with a runtime cost',fontsize=16,fontweight='bold',x=.60,y=1.005)
        fig.text(.60,.930,'Developer original: double precision with sparse storage. Small dots show three measured runs; large symbols show medians.',ha='center',fontsize=9.5,color='#53636F')
        large_pair=next((p for p in paired if p['case']=='sparse_sg99_fine9_t4' and p['tag']=='sparse_final' and p['reference']=='double' and p['variant']=='dictionary'),None)
        if large_pair:
            fig.text(.60,.883,f"99 groups x 9 heights: {large_pair['peak_commit_reduction_pct_median']:.1f}% less peak commit; {-large_pair['runtime_reduction_pct_median']:.1f}% longer runtime than PR #64.",ha='center',fontsize=10,fontweight='bold',color='#087E8B')
        fig.subplots_adjust(left=.37,right=.98,top=.80,bottom=.18,wspace=.20)
        save(fig,out/'01_time_memory',{'input_sha256':origins,'plotted_cases':keys,'runtime_reference':'double','memory':'absolute peak process commit MiB','paired_rows':[p for p in pairs if p['reference']=='double'],'variant_medians':medians})
        plt.close(fig)
    # Largest family of otherwise identical inputs with at least three worker counts.
    families=defaultdict(list)
    for key,c in conditions.items():
        if not any((m['tag'],m['case'])==key for m in medians): continue
        signature=tuple(str(c.get(k)) for k in ('pps','tau','kind','sources','sg','length','flow','conc','slices','speed','sc','hot','buildings','adaptive','transient','terrain'))
        families[signature].append(key)
    choices=[ks for ks in families.values() if len({conditions[k].get('workers') for k in ks})>=3]
    if choices:
        keys=max(choices,key=lambda ks:len({conditions[k].get('workers') for k in ks}))
        # Preserve tag/case medians and aggregate no unrelated workloads.
        fig,axs=plt.subplots(1,2,figsize=(12,5))
        plotted=[]
        for v in VARIANTS:
            rows=sorted([m for m in medians if (m['tag'],m['case']) in keys and m['variant']==v],key=lambda m:m['condition']['workers'])
            plotted.extend(rows)
            for ax,metric in zip(axs,('wall_s_median','peak_commit_mib_median')):
                ax.plot([m['condition']['workers'] for m in rows],[m[metric] for m in rows],marker=MARKERS[v],color=COLORS[v],lw=1.6,linestyle='--' if v=='dictionary_fixed' else '-',label=LABELS[v])
        for ax in axs:
            ax.set_xlabel('Configured workers'); ax.set_xticks(sorted({conditions[k]['workers'] for k in keys})); ax.grid(alpha=.2)
        axs[0].set_ylabel('Whole-process runtime (s)'); axs[1].set_ylabel('Peak process commit (MiB)')
        axs[0].set_title('Time spent in the complete run'); axs[1].set_title('Memory used by the complete process')
        example=conditions[keys[0]]
        fig.suptitle(f"Worker scaling | {example.get('sg')} groups, {example.get('pps'):,} particles/s, {example.get('conc')} m grid",fontsize=15,fontweight='bold')
        fig.legend(*axs[0].get_legend_handles_labels(),loc='lower center',ncol=2,frameon=False,bbox_to_anchor=(.5,-.015))
        fig.subplots_adjust(top=.80,bottom=.20,wspace=.28)
        save(fig,out/'02_worker_scaling',{'input_sha256':origins,'rows':plotted})
        plt.close(fig)
    # Use paired three-weather diagnostic with original/fixed/double, even if original fails.
    candidates=[]
    for r in records:
        if r['variant']=='double' and len(r.get('situation_sums',{}))>=3:
            key=(r['tag'],r['case'],r['repeat'])
            variants={x['variant']:x for x in records if (x['tag'],x['case'],x['repeat'])==key}
            if all(v in variants for v in ('dictionary','dictionary_fixed')): candidates.append((key,variants))
    if candidates:
        key,variants=next((x for x in candidates if x[0]==('load_transient','transient_three_t1',1)),candidates[0])
        weather=sorted(variants['double']['situation_sums'])
        fig,axs=plt.subplots(1,2,figsize=(13,4.8),gridspec_kw={'width_ratios':[1.06,1]})
        axs[0].axis('off')
        axs[0].text(0,1.09,'The reset must preserve carried particles',fontsize=14,fontweight='bold',va='top')
        blocks=[('1','Carried particles accumulate concentration.'),('2','New-particle driver begins.'),('3','Original branch clears the dictionary here.'),('4','Carried-particle concentration is missing from output.')]
        for i,(n,t) in enumerate(blocks):
            y=.80-i*.18
            axs[0].text(.01,y,n,weight='bold',color='white',bbox={'boxstyle':'circle,pad=.35','fc':'#B55544' if i==2 else '#087E8B','ec':'none'})
            axs[0].text(.09,y,t,va='center',fontsize=10.5,wrap=True)
        axs[0].text(0,.015,'Local correction: remove the redundant clear.\nThe output writer already clears the dictionaries.',fontsize=10.5,color='#087E8B',va='bottom')
        plotted=[]
        for v in ('double','dictionary','dictionary_fixed'):
            row=variants[v]
            ratios=[100*row['situation_sums'].get(w,0)/variants['double']['situation_sums'][w] if variants['double']['situation_sums'][w] else 0 for w in weather]
            axs[1].plot(range(1,len(weather)+1),ratios,marker=MARKERS[v],color=COLORS[v],lw=1.7,label=LABELS[v],alpha=.95)
            plotted.append({'variant':v,'concentration_sum_pct_of_double':ratios,'status':row['status'],'raw_sums':row['situation_sums']})
        axs[1].set_xticks(range(1,len(weather)+1)); axs[1].set_xlabel('Successive weather situation')
        axs[1].set_ylabel('Output concentration sum / PR #64 double (%)')
        axs[1].set_title('Three-weather transient diagnostic',fontsize=13,pad=14)
        axs[1].set_ylim(-3,108); axs[1].grid(alpha=.2); axs[1].legend(loc='lower left',frameon=False,fontsize=9)
        fig.subplots_adjust(left=.04,right=.99,bottom=.17,top=.91,wspace=.21)
        fig.text(.04,.035,f"Diagnostic {key[0]} / {key[1]} / repeat {key[2]}. Incorrect-output runs are not counted as performance gains.",fontsize=9.5,color='#53636F')
        save(fig,out/'03_transient_regression',{'input_sha256':origins,'selected_key':key,'weather_files':weather,'rows':plotted})
        plt.close(fig)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--job',type=Path,required=True); p.add_argument('--tags',nargs='*'); p.add_argument('--plots',action='store_true')
    args=p.parse_args(); out=args.job/'qa'/'presentation'; out.mkdir(parents=True,exist_ok=True)
    records,comps,conditions,origins,skipped=read_all(args.job/'results',set(args.tags or []))
    medians,pairs,paired,fidelity,excluded=summarize(records,comps,conditions)
    measured=[r for r in records if r.get('measured')]
    summary={'method':{'performance':'Measured pass/pass pairs with identical tag, case and repeat. Median of paired relative reductions, not ratio of separate medians. Positive reduction means less time or memory. Warmups and failed runs excluded.',
                       'memory':'Windows peak process commit (PeakPagefileUsage) and peak working set, in MiB. Whole-process metrics, not dictionary allocation alone.',
                       'occupancy':'Fraction of nonzero saved concentration values, not a direct count of dictionary keys; tiny accumulated doubles may round to zero in float output.',
                       'fidelity':'Paired comparisons include failed outputs to expose regressions. Relative L1 is sum absolute differences divided by reference sum.'},
             'tags':sorted({r['tag'] for r in records}),'skipped_incomplete_tags':skipped,'run_count':len(records),'measured_run_count':len(measured),
             'successful_measured_run_count':sum(r['status']=='pass' for r in measured),'excluded_runs':excluded,
             'conditions':[dict(c,tag=tag) for (tag,_),c in sorted(conditions.items())], 'variant_medians':medians,'paired_summaries':paired,'input_hashes':origins}
    dump(out/'summary.json',summary); dump(out/'paired_values.json',pairs); dump(out/'fidelity_pairs.json',fidelity)
    csv_write(out/'variant_medians.csv',medians); csv_write(out/'paired_values.csv',pairs); csv_write(out/'paired_summaries.csv',paired); csv_write(out/'fidelity_pairs.csv',fidelity); csv_write(out/'excluded_runs.csv',excluded)
    if args.plots: plots(out,records,medians,pairs,paired,conditions,origins)
    print(json.dumps({'runs':len(records),'measured':len(measured),'cases':len(conditions),'paired_summaries':len(paired),'excluded':len(excluded),'skipped':skipped}))

if __name__=='__main__': main()






