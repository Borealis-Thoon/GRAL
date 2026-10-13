from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import argparse
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path(__file__).resolve().parent);a=p.parse_args()
P=a.out;P.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig=plt.figure(figsize=(12.8,5.6),facecolor='white')
gs=fig.add_gridspec(1,2,width_ratios=[1.4,1],left=.085,right=.97,bottom=.23,top=.73,wspace=.35)
ax=fig.add_subplot(gs[0]); ar=fig.add_subplot(gs[1])
f=np.float32(16777216);d=float(f);fv=[0];dv=[0]
for i in range(100):
 f=np.float32(f+np.float32(1));d+=1;fv.append(float(f)-16777216);dv.append(float(np.float32(d))-16777216)
ax.plot(range(101),dv,color='#12766A',lw=2.5,label='Double sum, converted to float for output')
ax.plot(range(101),fv,color='#B26A38',lw=2.5,label='Float sum after every addition')
ax.set(xlabel='Number of +1 contributions',ylabel='Contribution retained in the final value',ylim=(-8,112))
ax.set_title('Small contributions survive accumulation',loc='left',fontweight='bold',pad=16)
ax.grid(axis='y',alpha=.2);ax.legend(loc='upper left',frameon=False,fontsize=8.5)
ax.text(100,105,'100 retained',ha='right',color='#12766A',weight='bold');ax.text(100,5,'0 retained',ha='right',color='#B26A38',weight='bold')
ar.bar([0,1],[15,0],width=.55,color=['#B26A38','#12766A']);ar.scatter([1],[0],s=75,color='#12766A',zorder=3)
ar.set(xticks=[0,1],xticklabels=['V2701','#64'],ylabel='Maximum changed cells out of 7,200',ylim=(0,18))
ar.set_title('The five repeated runs agreed',loc='left',fontweight='bold',pad=16);ar.grid(axis='y',alpha=.2);ar.set_axisbelow(True)
for x,y in [(0,15),(1,0)]:ar.text(x,y+.5,str(y),ha='center',weight='bold',fontsize=16)
fig.text(.04,.94,'Keep small concentration contributions in the accumulated result',fontsize=19,weight='bold')
fig.text(.04,.88,'#64: accumulate in double precision, then write the existing float output',fontsize=12,color='#555555')
fig.text(.04,.09,'Left: arithmetic example starting at 16,777,216. Right: measured whole-engine repeatability at 833.3 particles/s for 120 s,',fontsize=10)
fig.text(.04,.05,'8 point sources, 20 m cells and 4 workers. Largest baseline relative cell difference: 0.000187%.',fontsize=10)
for suffix in ['png','svg']:fig.savefig(P/f'precision_benefit.{suffix}',dpi=160,facecolor='white')
payload={'arithmetic_start':16777216,'additions':100,'increment':1,'float_result':int(f),'double_then_float_result':int(np.float32(d)),
 'engine_repeatability':{'requested_particles_per_second':100000/120,'duration_s':120,'source_count':8,'resolution_m':20,'workers':4,'repeats':5,'cell_count':7200,'max_changed_cells_baseline':15,'max_changed_cells_pr64':0,'max_relative_baseline_cell_difference_percent':.000187},
 'engine_evidence':'https://github.com/Borealis-Thoon/GRAL/blob/cb06f655aa78e2fdfe627cae3edf7f12481a3cfb/reviewer_response_20261013/README.md',
 'scope':'Arithmetic example and previously published measured repeatability; no new runtime claim.'}
(P/'figure_data.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
print('[FIGURE] precision_benefit.png/svg')
