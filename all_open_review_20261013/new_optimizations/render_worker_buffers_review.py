from pathlib import Path
import json,os
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).parent/'mpl_cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
P=Path(__file__).resolve().parent;data=json.loads((P/'worker_buffers_review_data.json').read_text());rows=data['rows']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False})
fig,(left,right)=plt.subplots(1,2,figsize=(14,6.4),gridspec_kw={'width_ratios':[1.5,1]})
fig.subplots_adjust(left=.28,right=.97,bottom=.18,top=.76,wspace=.33)
fig.text(.045,.955,'Worker concentration buffers: time and memory',fontsize=23,weight='bold',color='#183b48')
fig.text(.045,.895,'Same build with the option disabled or enabled. Five interleaved runs per mode.',fontsize=12,color='#526773')
colors={'disabled':'#9ba8b1','enabled':'#007f94'}
for ax,title in [(left,'Whole-process time (s)'),(right,'Peak working set (MiB)')]:
 ax.set_title(title,loc='left',fontsize=13,pad=15,weight='bold');ax.set_ylim(3.5,-.55);ax.grid(axis='x',color='#e9edef');ax.set_axisbelow(True);ax.tick_params(axis='y',length=0);ax.set_yticks(range(4))
left.set_yticklabels([r['label'] for r in rows]);right.set_yticklabels([])
for i,row in enumerate(rows):
 for key,offset in [('disabled',-.17),('enabled',.17)]:
  d=row[key];t=d['median_s'];y=i+offset
  left.barh(y,t,height=.27,color=colors[key]);left.errorbar(t,y,xerr=[[t-d['min_s']],[d['max_s']-t]],fmt='none',ecolor='#34444f',capsize=3,lw=1)
  left.text(d['max_s']+.035,y,f'{t:.3f}',va='center',fontsize=10)
  memory=d['peak_working_set']/2**20;right.barh(y,memory,height=.27,color=colors[key]);right.text(memory+4,y,f'{memory:.1f}',va='center',fontsize=10)
left.set_xlim(0,3.45);right.set_xlim(0,330)
fig.legend(handles=[Patch(color=colors['disabled'],label='Disabled'),Patch(color=colors['enabled'],label='Enabled')],loc='upper right',bbox_to_anchor=(.96,.89),ncol=2,frameon=False)
fig.text(.045,.10,'The million-particle case used 0.177 MiB of buffers; the dense grid used 196.225 MiB.',fontsize=11,color='#334d5b')
fig.text(.045,.055,'Option off by default. Runtime whiskers show the observed minimum and maximum; peak memory is the maximum across runs.',fontsize=10,color='#526773')
for ext in ['png','svg']:fig.savefig(P/f'worker_buffers_review.{ext}',dpi=170,facecolor='white')
print('[FIGURE] worker_buffers_review.png/svg')
