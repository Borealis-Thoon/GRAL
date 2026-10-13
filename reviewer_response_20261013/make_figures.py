from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'figures'; OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','savefig.facecolor':'white'})
COLORS=['#586776','#c27b35','#197a78']
def save(fig,name):
    for suffix in ['png','svg']: fig.savefig(OUT/f'{name}.{suffix}',dpi=160,bbox_inches='tight')
    plt.close(fig)
s=json.loads((ROOT/'residual/residual_combined_summary.json').read_text(encoding='utf-8-sig'))
rows={(r['case'],r['variant']):r for r in s['summaries']}
fig,ax=plt.subplots(1,2,figsize=(12.6,5.3),gridspec_kw={'wspace':.38})
fig.subplots_adjust(top=.79,bottom=.18)
fig.suptitle('Residual splitting needs a conditional policy',x=.075,y=1.01,ha='left',fontsize=18,fontweight='bold')
for a,case,title in zip(ax,['largeoff_10m_n3000','many_sources_10m_requested100'],['Strong source switches off\n10 m grid; 3,000 fresh particles','Every eligible entry already has one particle\n10 m grid; request 100, actual allocation 640']):
    vals=[rows[(case,v)]['selected_children_sum'] for v in ['baseline','pr62','pr63']]
    bars=a.bar(['V2701','#62','#62 + #63'],vals,color=COLORS,width=.65)
    a.bar_label(bars,labels=[f'{v:,.0f}' for v in vals],padding=7,fontsize=12,fontweight='bold')
    a.set_ylim(0,max(vals)*1.29); a.set_title(title,loc='left',fontsize=12,pad=16)
    a.set_ylabel('Residual releases, sum of four situations')
    a.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}')); a.set_axisbelow(True); a.grid(axis='y',alpha=.18)
ax[0].text(0,-.24,'#63 reduces releases by 78.7% versus #62.\nCounts remain 11.6 times the V2701 total.',transform=ax[0].transAxes,va='top',fontsize=11)
ax[1].text(0,-.24,'No releases saved by the planner.\nDiagnostic planning: 0.45 → 5.79 ms.',transform=ax[1].transAxes,va='top',fontsize=11)
fig.text(.075,-.12,'20 conditions / 240 Main runs. Concentration fields change in some cases; accuracy was not established.\nDiagnostic timings use separate instrumented builds and do not measure whole-model speedup.',fontsize=9,color='#555555',va='top')
save(fig,'residual_policy')

f=json.loads((ROOT/'f_opt/results/review_summary.json').read_text(encoding='utf-8-sig'))
fig,ax=plt.subplots(1,2,figsize=(12.8,5.3),gridspec_kw={'wspace':.40})
fig.subplots_adjust(top=.79,bottom=.18)
fig.suptitle('Double accumulation: repeatability and memory cost',x=.075,y=1.01,ha='left',fontsize=18,fontweight='bold')
a=ax[0]
a.set_xlim(-.8,4.1); a.set_ylim(-.7,1.8)
a.set_xticks(range(4),['Repeat 2','Repeat 3','Repeat 4','Repeat 5'])
a.set_yticks([1,0],['V2701','#64'])
a.set_title('Same seed, 4 workers, 100,000 particles\nEach repeat compared with its first run',loc='left',fontsize=12,pad=16)
from matplotlib.patches import Rectangle
for y,color,word in [(1,'#c27b35','Different'),(0,'#197a78','Same')]:
    for x in range(4):
        a.add_patch(Rectangle((x-.42,y-.3),.84,.6,facecolor=color,edgecolor='none'))
        a.text(x,y,word,color='white',ha='center',va='center',fontsize=10,fontweight='bold')
for spine in a.spines.values(): spine.set_visible(False)
a.tick_params(length=0)
a.text(0,-.22,'Baseline: at most 15 changed cells;\nmaximum relative cell difference 0.000187%.\n#64: identical outputs in these four comparisons.',transform=a.transAxes,va='top',fontsize=10.5)
a=ax[1]
mem=[m for m in json.loads((ROOT/'f_opt/component/result.json').read_text(encoding='utf-8-sig'))['memory'] if m['name'] in ['reported_500m_shape','same_domain_250m_shape']]
payload=[m['payload_bytes']/2**20 for m in mem]
overhead=[m['jagged_and_closure_overhead_bytes']/2**20 for m in mem]
a.barh([1,0],payload,height=.48,color='#197a78',label='double payload')
a.barh([1,0],overhead,left=payload,height=.48,color='#91aaa6',label='array / allocation overhead')
for y,p,o in zip([1,0],payload,overhead): a.text(p+o+5,y,f'{p+o:.2f} MiB',va='center',fontweight='bold',fontsize=11)
a.set_xlim(0,365); a.set_ylim(-.65,1.8); a.set_yticks([1,0],['500 m\n114 × 82','250 m\n228 × 164'])
a.set_title('Added double-array allocation, measured\n9 output slices; 108 source groups',loc='left',fontsize=12,pad=16)
a.set_xlabel('Allocated memory (MiB)'); a.legend(frameon=False,loc='lower right',fontsize=9)
a.text(0,-.22,'Historical whole-process sampled peaks:\n2.17 GiB (500 m), 3.39 GiB (250 m).\nThose runs used a different storage layout.',transform=a.transAxes,va='top',fontsize=10.5)
fig.text(.075,-.14,'The array test measures the current PR layout; historical peaks are context, not paired PR overhead.\nThis small repeated-run test does not guarantee bitwise equality in arbitrary parallel simulations.',fontsize=9,color='#555555',va='top')
save(fig,'precision_memory')

import csv
# Ratios below use each baseline median, not medians of paired speed ratios.
comparison=f['wall_comparison']
fig,axes=plt.subplots(1,2,figsize=(13,5.7),gridspec_kw={'wspace':.65})
fig.suptitle('Current PR timings do not establish an overall speedup',x=.075,y=1.01,ha='left',fontsize=17,fontweight='bold')
cases=['small_point','hot_stacks','terrain_area','many_sources','dense_output_grid','parallel_concentrated']
names=['Small point sources','Hot stacks','Terrain / area sources','512 mixed sources','Dense output grid','4-worker concentrated']
colors={'f64':'#197a78','opt68_69':'#bd803a','f64_opt68_69':'#696099'}
labels={'f64':'#64','opt68_69':'#68 + #69','f64_opt68_69':'#64 + #68 + #69'}
for vi,v in enumerate(colors):
    for i,c in enumerate(cases):
        r=next(x for x in comparison if x['case']==c and x['variant']==v)
        base=r['median_wall_s']/(1+r['median_wall_change_pct']/100)
        value=r['median_wall_s']/base
        axes[0].errorbar(value,i+(vi-1)*.20,xerr=[[value-r['min_wall_s']/base],[r['max_wall_s']/base-value]],fmt='o',markersize=5,color=colors[v],capsize=2,label=labels[v] if i==0 else None)
        axes[1].plot(r['median_peak_commit_delta_mib'],i+(vi-1)*.20,'o',color=colors[v],markersize=5)
axes[0].axvline(1,color='#888888',lw=1,ls='--'); axes[1].axvline(0,color='#888888',lw=1,ls='--')
for a in axes:
    a.set_yticks(range(6),names); a.invert_yaxis(); a.grid(axis='x',alpha=.2); a.set_axisbelow(True)
axes[0].set_xlabel('Whole-run time / baseline median\nDot: median; whisker: full range of 5 runs')
axes[1].set_xlabel('Median peak process commit increase (MiB)\nVersus baseline median')
axes[0].set_title('Runtime, including startup and output',loc='left',fontsize=12,pad=14)
axes[1].set_title('Memory cost rises with output-grid size',loc='left',fontsize=12,pad=14)
axes[0].legend(frameon=False,loc='upper center',bbox_to_anchor=(.5,-.20),ncol=3,fontsize=9)
fig.text(.075,-.13,'120 Main runs on V2701 891225b2; six synthetic conditions, four variants, five interleaved repeats.\nThese short runs do not reproduce the historical full OPT1 package or measure an all-PR production speedup.',fontsize=9,color='#555555',va='top')
save(fig,'runtime_tradeoffs')
