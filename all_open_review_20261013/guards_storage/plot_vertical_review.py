from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parent
data=json.loads((ROOT/'vertical_review.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none'})
fig=plt.figure(figsize=(13,7.2),facecolor='white')
fig.text(.055,.935,'Half of lookups reused; the engine trials remained slightly slower',fontsize=18,weight='bold',color='#20323d')
fig.text(.055,.888,'Vertical-index reuse in GRAL #69',fontsize=13,color='#637780')
left=fig.add_axes([.06,.33,.28,.43]);left.axis('off')
left.text(0,1.04,'Earlier terrain instrumentation',weight='bold',fontsize=13)
left.text(0,.88,'889,446 lookup requests',color='#637780',fontsize=12)
left.barh([.62],[444724/889446],left=0,height=.16,color='#087f92')
left.barh([.62],[444722/889446],left=444724/889446,height=.16,color='#d3dce1')
left.text(.25,.62,'50%',ha='center',va='center',weight='bold',color='white',fontsize=23)
left.text(0,.41,'444,724 reused indices',weight='bold',color='#087f92',fontsize=13)
left.text(0,.24,'Two instrumented terrain projects\nwith 39 vertical layers.',color='#637780',fontsize=11,linespacing=1.7)
left.set_xlim(0,1);left.set_ylim(0,1)
right=fig.add_axes([.48,.27,.45,.47])
right.set_title('Independent whole-engine comparison',loc='left',fontweight='bold',fontsize=13,pad=36)
labels=['Area sources\nStable, low wind','Hot point sources\nNine slices'];colors=['#84939a','#087f92','#c46b2d'];names=['Original search','Current PR #69','Height-first trial']
for ci,c in enumerate(['terrain_area','terrain_hot_points']):
 for vi,v in enumerate(['baseline','current','height_first']):
  ss=next(s for s in data['summaries'] if s['case']==c and s['variant']==v);y=ci+(vi-1)*.20
  right.barh(y,ss['median_wall_s'],height=.16,color=colors[vi],alpha=.92,label=names[vi] if ci==0 else None)
  right.scatter(ss['wall_s'],[y]*5,s=15,facecolor='white',edgecolor='#263b46',linewidth=.7,zorder=3)
  right.text(max(ss['wall_s'])+.08,y,f"{ss['median_wall_s']:.3f} s",va='center',fontsize=10)
right.set_yticks([0,1],labels);right.invert_yaxis();right.set_xlim(0,5.4);right.set_xlabel('Whole-process wall time (seconds)');right.grid(axis='x',alpha=.18);right.set_axisbelow(True)
right.legend(loc='upper center',bbox_to_anchor=(.5,1.16),ncol=3,frameon=False,fontsize=8.8,columnspacing=.8)
for side in ['top','right','left']:right.spines[side].set_visible(False)
right.tick_params(axis='y',length=0,pad=9)
fig.text(.48,.19,'Bars: medians. Dots: five interleaved timed runs per variant.',fontsize=10,color='#637780')
fig.text(.055,.115,'100,000 requested particles | 26 source groups | 20 m grid | one worker',fontsize=11,color='#20323d')
fig.text(.055,.072,'All 36 runs matched concentration payloads. Six warmups were excluded from timing.',fontsize=11,color='#637780')
out=ROOT/'figures';out.mkdir(exist_ok=True)
fig.savefig(out/'vertical_reuse_review.png',dpi=170);fig.savefig(out/'vertical_reuse_review.svg');plt.close(fig)
