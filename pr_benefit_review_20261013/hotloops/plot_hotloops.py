from pathlib import Path
import argparse,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args()
r=json.loads(a.results.read_text());a.out_dir.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','svg.fonttype':'none'})
lookup={(x['case'],x['variant']):x for x in r['summaries']}
labels=['100/s, 120 s\n26 area sources\nStable terrain','1,000/s, 180 s\n64 hot point sources\nUnstable terrain','500/s, 240 s\n128 mixed sources\nUnstable flat field','1,000/s, 300 s\n64 area sources\nUnstable flat field']
def save(fig,name):
 for ext in ['png','svg']:fig.savefig(a.out_dir/(name+'.'+ext),dpi=190,bbox_inches='tight',facecolor='white')
 plt.close(fig)
fig,ax=plt.subplots(figsize=(11.5,5.8));rates=np.array([100,1000,8000]);x=np.arange(3);w=.32
for i,(ns,bytes_per,color) in enumerate([(1,32,'#267b9d'),(9,64,'#5da576')]):
 values=bytes_per*rates*3600/1e6
 bars=ax.bar(x+(i-.5)*w,values,w,label=f'{ns} concentration slice'+('s' if ns>1 else ''),color=color)
 for b,v in zip(bars,values):ax.text(b.get_x()+b.get_width()/2,b.get_height()+25,f'{v:,.1f}',ha='center',va='bottom',fontsize=11)
ax.set_xticks(x,[f'{v:,} particles/s' for v in rates]);ax.set_ylabel('Managed heap allocation avoided per simulated hour (MB)');ax.set_ylim(0,2150);ax.legend(frameon=False,loc='upper left');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
fig.suptitle('A small array avoided on every fresh-particle call',x=.075,ha='left',fontsize=19,fontweight='bold')
fig.text(.075,.915,'#68 uses bounded stack storage for the concentration-slice indices.',fontsize=12)
fig.subplots_adjust(top=.82,bottom=.19,left=.10,right=.98)
fig.text(.075,.055,'Calculated from measured savings of 32 B/call (one slice) and 64 B/call (nine slices).\nThese are cumulative allocations: the live process footprint is much smaller. MB = 1,000,000 bytes.',fontsize=10,color='#444444')
save(fig,'slice_allocation_rates')
fig,ax=plt.subplots(figsize=(10.4,5.8));selected=[r['cases'][1],r['cases'][3]];x=np.arange(2);w=.3
for offset,v,label,color in [(-.5,'baseline','Heap array per particle','#98a6b0'),(.5,'pr68','Bounded stack buffer','#267b9d')]:
 runs=[[q['memory']['PeakWorkingSetSize']/1048576 for q in r['records'] if q['case']==c['id'] and q['variant']==v and q['measured']] for c in selected]
 med=np.array([np.median(z) for z in runs]);ax.bar(x+offset*w,med,w,label=label,color=color,yerr=np.array([[m-min(z) for m,z in zip(med,runs)],[max(z)-m for m,z in zip(med,runs)]]),capsize=3,error_kw={'elinewidth':1})
 for i,m in enumerate(med):ax.text(i+offset*w,m+2,f'{m:.2f}',ha='center',fontsize=12)
for i,c in enumerate(selected):
 b=lookup[(c['id'],'baseline')]['median_peak_working_bytes'];m=lookup[(c['id'],'pr68')]['median_peak_working_bytes']
 ax.text(i,b/1048576+15,f'{100*(1-m/b):.1f}% less peak memory',ha='center',fontsize=12,fontweight='bold',color='#267b9d')
ax.set_xticks(x,['Hot point sources over terrain\n180 s, 64 sources','Area sources on a flat field\n300 s, 64 sources']);ax.set_ylabel('Peak process working set (MiB)');ax.set_ylim(0,160);ax.grid(axis='y',alpha=.17);ax.set_axisbelow(True);ax.legend(frameon=False,loc='upper left')
fig.suptitle('Nine-slice runs use less peak memory',x=.085,ha='left',fontsize=20,fontweight='bold');fig.text(.085,.92,'#68 removes the heap array created for every fresh particle.',fontsize=12)
fig.subplots_adjust(top=.83,bottom=.23,left=.09,right=.98)
fig.text(.085,.05,'1,000 particles/s, 26 source groups, nine output slices, one worker. Five-run medians and ranges.\nWhole-process time changed by +0.27% and +1.54%, respectively; concentration payloads matched.',fontsize=10,color='#444444')
save(fig,'slice_memory_effects')
fig,axes=plt.subplots(1,3,figsize=(15,6.2),sharey=True)
for ax,v,name in zip(axes,['pr68','pr69','pr72'],['#68  Slice stack storage','#69  Vertical-index reuse','#72  Unstable-variance reuse']):
 values=[-lookup[(c['id'],v)]['percent_change_vs_baseline'] for c in r['cases']]
 y=np.arange(4);bars=ax.barh(y,values,color=['#288667' if z>0 else '#c46a32' for z in values])
 ax.axvline(0,color='#777777',lw=.8);ax.set_title(name,fontsize=12);ax.set_xlabel('Whole-process time saved (%)');ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
 ax.set_xlim(min(-5,min(values)-3),max(5,max(values)+3));ax.set_yticks(y,labels);ax.invert_yaxis()
 for b,z in zip(bars,values):ax.text(z+(.2 if z>=0 else -.2),b.get_y()+b.get_height()/2,f'{z:+.1f}%',ha='left' if z>=0 else 'right',va='center',fontsize=10)
fig.suptitle('Independent engine trials at 100 to 1,000 particles/s',x=.04,ha='left',fontsize=19,fontweight='bold')
fig.text(.04,.90,'Each PR was applied alone to the same upstream revision. Green means less elapsed time.',fontsize=12)
fig.subplots_adjust(left=.16,right=.97,top=.82,bottom=.15,wspace=.30)
fig.text(.04,.03,'Five interleaved timed runs after one warmup per variant and condition; fixed seeds, one worker.\nMedian whole-process times include initialization and output. All concentration payloads matched.',fontsize=10,color='#444444')
save(fig,'independent_runtime')
fig,ax=plt.subplots(figsize=(11.5,6.1));x=np.arange(4);w=.33
for offset,v,label,color in [(-.5,'baseline','Original calculation','#9ca8b1'),(.5,'pr72','Reuse repeated inputs','#288667')]:
 med=np.array([lookup[(c['id'],v)]['median_wall_s'] for c in r['cases']]);runs=[lookup[(c['id'],v)]['wall_s'] for c in r['cases']]
 ax.bar(x+offset*w,med,w,label=label,color=color,yerr=np.array([[m-min(z) for m,z in zip(med,runs)],[max(z)-m for m,z in zip(med,runs)]]),capsize=3,error_kw={'elinewidth':1})
 for i,m in enumerate(med):ax.text(i+offset*w,m+.09,f'{m:.2f}',ha='center',va='bottom',fontsize=10)
ax.set_xticks(x,labels);ax.set_ylabel('Whole-process elapsed time (s)');ax.legend(frameon=False);ax.set_ylim(0,ax.get_ylim()[1]*1.15);ax.grid(axis='y',alpha=.17);ax.set_axisbelow(True)
for i,c in enumerate(r['cases'][1:],start=1):
 saving=-lookup[(c['id'],'pr72')]['percent_change_vs_baseline'];top=max(max(lookup[(c['id'],v)]['wall_s']) for v in ['baseline','pr72'])
 ax.text(i,top+.55,f'{saving:.1f}% less time',ha='center',fontsize=11,fontweight='bold',color='#288667')
fig.suptitle('Unstable runs finish 2.4% to 3.6% sooner',x=.075,ha='left',fontsize=20,fontweight='bold')
fig.text(.075,.895,'#72 avoids repeating the power expression within each particle trajectory.',fontsize=12)
fig.subplots_adjust(top=.83,bottom=.24,left=.08,right=.98)
fig.text(.075,.05,'Bars show medians; whiskers show the five-run range. One worker, fixed seeds.\nThe stable branch keeps its existing formula. All concentration payloads matched.',fontsize=10,color='#444444')
save(fig,'unstable_variance_realistic_rates')
