from pathlib import Path
import argparse, csv, hashlib, json, os, shutil, statistics

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--public',type=Path,required=True);a=parser.parse_args();root=a.root;pub=a.public;pub.mkdir(parents=True,exist_ok=True)
    os.environ['MPLCONFIGDIR']=str(root/'mpl_cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    summary_path=root/'main/summary.json' if (root/'main/summary.json').exists() else root/'summary.json'
    s=json.loads(summary_path.read_text());by={(r['case'],r['variant']):r for r in s['summaries']}
    ordered=['concentrated_8000','typical_1000','longer_32_sources','fine_9_heights','tutorial_100']
    labels={
      'concentrated_8000':'8,000/s for 120 s | 2 point sources\n40 m grid, unstable, 24 workers',
      'typical_1000':'1,000/s for 120 s | 8 point sources\n40 m grid, neutral, 24 workers',
      'longer_32_sources':'1,000/s for 300 s | 32 spread-out point sources\n40 m grid, stable, 24 workers',
      'fine_9_heights':'1,000/s for 120 s | 8 area sources\n10 m grid, 9 output heights, 24 workers',
      'tutorial_100':'100/s for 60 s | 2 point sources\n40 m grid, stable, 4 workers',
    }
    rows=[]
    for name in ordered:
        off=by[name,'off'];on=by[name,'on'];before=by[name,'before'];ps=on['paired_savings_percent']
        rows.append(dict(case=name,before64_s=before['median_s'],off_s=off['median_s'],on_s=on['median_s'],saved_percent=on['ratio_of_medians_savings_percent'],paired_min_percent=min(ps),paired_max_percent=max(ps),faster_pairs=sum(x>0 for x in ps),pairs=len(ps),buffer_MiB=on['buffer_bytes']/2**20,off_peak_working_set_MiB=off['median_peak_working_set']/2**20,on_peak_working_set_MiB=on['median_peak_working_set']/2**20))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,'axes.axisbelow':True,'svg.fonttype':'none'})
    fig=plt.figure(figsize=(13.8,7.4),facecolor='white')
    ax=fig.add_axes([.345,.22,.40,.61]);tab=fig.add_axes([.775,.22,.205,.61]);tab.axis('off')
    y=np.arange(len(rows));vals=[r['saved_percent'] for r in rows];colors=['#177c7a' if r['paired_min_percent']>0 else '#909ba3' for r in rows]
    ax.barh(y,vals,color=colors,height=.54,alpha=.88)
    for i,(r,c) in enumerate(zip(rows,ordered)):
        p=by[c,'on']['paired_savings_percent'];ax.plot([min(p),max(p)],[i,i],color='#364954',lw=1)
        ax.scatter(p,np.full(len(p),i),s=18,color='#253c4c',zorder=3)
        label='No clear gain' if c=='tutorial_100' else f"{r['saved_percent']:.1f}%"
        ax.text(max(vals[i],max(p))+2,i,label,va='center',weight='bold',color='#164f50' if vals[i]>0 else '#5c6670')
        decimals=4 if c=='tutorial_100' else 3
        tab.text(.00,i,f"{r['off_s']:.{decimals}f} → {r['on_s']:.{decimals}f}",va='center',fontsize=11)
        tab.text(.86,i,f"{r['buffer_MiB']:.2f}",va='center',ha='right',fontsize=11)
    ax.set_yticks(y,labels=[labels[c] for c in ordered]);ax.tick_params(axis='y',length=0,pad=12)
    ax.set_ylim(4.65,-.65);tab.set_ylim(4.65,-.65);tab.set_xlim(0,1)
    ax.set_xlim(min(-8,min(r['paired_min_percent'] for r in rows)-3),max(max(r['paired_max_percent'] for r in rows)+12,60));ax.axvline(0,color='#77838c',lw=1);ax.grid(axis='x',color='#e3e8eb')
    ax.set_xlabel('Whole-process time saved when buffers are enabled (%)',labelpad=12)
    tab.text(0,-.9,'OFF → ON (s)',fontsize=11,weight='bold');tab.text(.86,-.9,'Buffer MiB',fontsize=11,weight='bold',ha='right')
    top=max(vals);fig.text(.032,.94,f'Worker-local sums cut runtime by up to {top:.1f}%',fontsize=21,weight='bold',color='#173b4d')
    fig.text(.032,.891,'The largest gains occur when many particle contributions share concentration cells.',fontsize=12,color='#425b67')
    fig.text(.035,.10,'Five interleaved OFF/ON pairs per field; one warmup per mode. Bars: ratio of median times. Dots: individual pairs.',fontsize=10.5,color='#425b67')
    fig.text(.035,.062,'A 16 MiB budget fits the first three fields and skips the 196.22 MiB allocation. The option stays off by default.',fontsize=10.5,color='#425b67')
    for ext in ['png','svg']:fig.savefig(pub/f'worker_buffers_benefit.{ext}',dpi=180,facecolor='white')
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12.2,4.4),facecolor='white');fig.subplots_adjust(left=.035,right=.98,bottom=.18,top=.81,wspace=.11)
    for ax in axes:ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
    def box(ax,x,y,w,h,text,color):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.01,rounding_size=.025',linewidth=1,edgecolor=color,facecolor=color+'18'));ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=11,color='#193743')
    def arrow(ax,a,b,color):ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=15,color=color,lw=1.6))
    left,right=axes
    left.set_title('Shared concentration sums',loc='left',fontsize=14,weight='bold',pad=14)
    for y0 in [.70,.40,.10]:box(left,.02,y0,.24,.16,'Worker', '#647a88');arrow(left,(.28,y0+.08),(.58,.48),'#bd7054')
    box(left,.59,.34,.35,.28,'Lock\nShared cell', '#bd7054')
    left.text(.61,.09,'Workers can wait\nfor the same lock.',fontsize=11,color='#6b4c43',ha='left')
    right.set_title('Worker-local sums, then merge',loc='left',fontsize=14,weight='bold',pad=14)
    for y0 in [.70,.40,.10]:box(right,.02,y0,.20,.16,'Worker','#647a88');arrow(right,(.23,y0+.08),(.34,y0+.08),'#177c7a');box(right,.36,y0,.27,.16,'Local buffer','#177c7a');arrow(right,(.65,y0+.08),(.78,.48),'#177c7a')
    box(right,.79,.34,.19,.28,'Merge\nonce','#177c7a')
    fig.text(.035,.92,'Avoid a shared lock at each new-particle concentration update',fontsize=19,weight='bold',color='#173b4d')
    fig.text(.035,.073,'Each worker adds to its own double buffer. After the particle loop, the driver adds these sums to the shared grid.',fontsize=11,color='#425b67')
    for ext in ['png','svg']:fig.savefig(pub/f'worker_buffers_method.{ext}',dpi=180,facecolor='white')
    plt.close(fig)
    with (pub/'measurements.csv').open('w',newline='',encoding='utf-8') as fcsv:w=csv.DictWriter(fcsv,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    shutil.copy2(summary_path,pub/'summary.json');shutil.copy2(root/'source_manifest.json',pub/'source_manifest.json');shutil.copy2(root/'builds.json',pub/'builds.json')
    for name in ['benchmark.py','field_support.py','apply_patch_helper.py']:shutil.copy2(root/name,pub/name)
    for name in ['reconstruct.py','present.py','check_budget.py']:shutil.copy2(Path(__file__).parent/name,pub/name)
    shutil.copytree(root/'patches',pub/'patches',dirs_exist_ok=True);shutil.copytree(root/'template',pub/'template',dirs_exist_ok=True)
    inputs=root/'main/inputs' if (root/'main/inputs').exists() else root/'inputs'
    shutil.copytree(inputs,pub/'inputs',dirs_exist_ok=True)
    if (root/'reconstruction_validation.json').exists():shutil.copy2(root/'reconstruction_validation.json',pub/'reconstruction_validation.json')
    budget_path=root/'budget16/summary.json' if (root/'budget16/summary.json').exists() else root/'budget16_summary.json'
    if budget_path.exists():shutil.copy2(budget_path,pub/'budget16_summary.json')
    qa=dict(status=s['status'],main_runs=s['main_runs'],timed_runs=s['timed_runs'],summary=rows,all_payload_pairs_equal=all(p['all_payload_equal'] for p in s['paired_comparisons']),max_relative_l1=max(p['relative_l1'] for p in s['paired_comparisons']),max_repeat_relative_l1=max((p['relative_l1'] for p in s['repeat_differences']),default=0),strict_builds=json.loads((root/'builds.json').read_text()))
    if budget_path.exists():qa['budget_fallback']=json.loads(budget_path.read_text());qa['total_main_runs']=s['main_runs']+qa['budget_fallback']['runs']
    (pub/'validation.json').write_text(json.dumps(qa,indent=2)+'\n',encoding='utf-8')
    print('[PUBLIC]',qa['status'],qa.get('total_main_runs',qa['main_runs']),'Main runs',len(list(pub.rglob('*'))),'entries')
if __name__=='__main__':main()
