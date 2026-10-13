from pathlib import Path
import csv,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
R=Path(__file__).resolve().parent
s=json.loads((R/'results/main_summary.json').read_text())
with (R/'results/timings.csv').open(newline='') as f: rows=list(csv.DictReader(f))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
blue='#167EA5';dark='#485465';warm='#B76A38';light='#E8EDF1'
fig,(a,b)=plt.subplots(1,2,figsize=(15.2,7.8),gridspec_kw={'width_ratios':[1.05,1.25]})
fig.subplots_adjust(left=.065,right=.965,top=.77,bottom=.27,wspace=.56)
fig.text(.065,.935,'Reuse unchanged unstable-condition variance',fontsize=23,fontweight='bold',color='#17283B')
fig.text(.065,.888,'Identical concentration output in 80 full-engine runs; less repeated work in unstable conditions.',fontsize=12,color=dark)
a.set_title('All five paired runs',loc='left',fontsize=14,fontweight='bold',pad=17)
for name,start in [('unstable_100k',0),('zr_30k',2.5)]:
 rs=[r for r in rows if r['case']==name]
 for rep in range(5):
  vals=[float(next(r['wall_s'] for r in rs if r['variant']==v and int(r['repeat'])==rep)) for v in ['met_baseline','met_variance']]
  shift=(rep-2)*.033
  a.plot([start+shift,start+1+shift],vals,color='#9DAAB4',lw=1,alpha=.8,zorder=1)
  a.scatter(start+shift,vals[0],s=36,color=dark,edgecolor='white',linewidth=.6,zorder=3)
  a.scatter(start+1+shift,vals[1],s=36,color=blue,edgecolor='white',linewidth=.6,zorder=3)
 med=next(x for x in s['summaries'] if x['case']==name)
 a.text(start+.5,.61,f"{med['baseline_median_s']:.3f} to {med['candidate_median_s']:.3f} s\n{100*(1-med['median_runtime_ratio']):.2f}% lower median",ha='center',va='top',fontsize=10,color='#17283B')
a.set_xticks([0,1,2.5,3.5],['Before','After','Before','After']);a.set_xlim(-.45,3.95);a.set_ylim(.5,1.65);a.set_yticks([.75,1,1.25,1.5]);a.set_ylabel('Whole-process elapsed time (seconds)');a.grid(axis='y',color=light,linewidth=.8);a.set_axisbelow(True)
a.text(.5,-.15,'100,000 particles\nFlat, unstable',ha='center',va='top',transform=a.get_xaxis_transform(),fontsize=11)
a.text(3,-.15,'30,000 particles\nZR input, unstable',ha='center',va='top',transform=a.get_xaxis_transform(),fontsize=11)
b.set_title('Median change across all eight conditions',loc='left',fontsize=14,fontweight='bold',pad=17)
names=[('unstable_100k','Flat unstable | 100,000'),('zr_30k','ZR unstable | 30,000'),('transient_unstable','Transient | 3,000'),('unstable_small','Flat unstable | 3,000'),('unstable_terrain','Terrain unstable | 30,000'),('sonic_30k','Sonic input | 30,000'),('stable_100k','Stable | 100,000'),('unstable_hot_mixed','Mixed / hot sources | 30,000')]
for i,(name,label) in enumerate(names):
 v=100*(next(x for x in s['summaries'] if x['case']==name)['median_runtime_ratio']-1);color=blue if v<0 else warm
 b.barh(i,v,height=.57,color=color,alpha=1 if i<2 else .65)
 b.text(v+(-.13 if v<0 else .13),i,f'{v:+.2f}%',ha='right' if v<0 else 'left',va='center',fontsize=10,color='#17283B',fontweight='bold' if i<2 else 'normal')
b.set_yticks(range(8),[x[1] for x in names],fontsize=10);b.invert_yaxis();b.set_xlim(-5.5,3.5);b.set_xticks([-4,-2,0,2]);b.axvline(0,color=dark,lw=.9);b.grid(axis='x',color=light,lw=.8);b.set_axisbelow(True);b.set_xlabel('Elapsed time change (%)    |    negative = faster',labelpad=12)
fig.text(.065,.075,'Five interleaved baseline/candidate pairs per condition, one worker. Whole-process time includes startup, flow preparation and output.',fontsize=9.6,color=dark)
fig.text(.065,.039,'All pairs were faster in the two highlighted cases. Timing ranges overlapped in the other six cases; their small changes should not be read as established gains.',fontsize=9.6,color=dark)
out=R/'figures';out.mkdir(exist_ok=True)
for ext in ['png','svg']:fig.savefig(out/('unstable_variance_runtime.'+ext),dpi=190,facecolor='white')
plt.close(fig);print('SAVED PNG SVG')
