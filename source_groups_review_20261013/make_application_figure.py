from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'application_context.json').read_text(encoding='utf-8-sig'))['measurements']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(figsize=(11.6,4.5)); fig.subplots_adjust(left=.15,right=.95,top=.70,bottom=.29)
fig.text(.06,.94,'108 time-partitioned source groups on a 32 GB desktop',fontsize=18,fontweight='bold')
fig.text(.06,.85,'Intel Core Ultra 7 270K Plus  |  22 workers  |  9 slices  |  108 completed situations',fontsize=11,color='#444444')
for i,r in enumerate(rows):
    y=1-i; value=r['sampled_peak_working_set_gib']; ax.barh(y,value,height=.45,color='#197a78')
    ax.text(value+.5,y,f"{value:.2f} GiB   /   {r['elapsed_minutes']:.2f} min",va='center',fontsize=11,fontweight='bold')
ax.axvline(31.47,color='#8f9397',ls='--',lw=1.5)
ax.text(31.47,1.48,'Recorded system RAM\n31.47 GiB',ha='right',va='bottom',fontsize=10,color='#555555')
ax.set_xlim(0,33);ax.set_ylim(-.6,1.8);ax.set_yticks([1,0],['500 m\n114 × 82 cells','250 m\n228 × 164 cells']);ax.set_xticks([0,8,16,24,32]);ax.set_xlabel('Sampled peak working set of the model process (GiB)')
ax.set_axisbelow(True);ax.grid(axis='x',alpha=.2)
fig.text(.06,.095,'Historical expanded engine with lazy source-group storage and extended filename coding.\nThis demonstrates feasibility at these scales; it does not measure the six-line patch’s overhead.\nThe 108 time-partitioned groups were not all emitting fresh particles simultaneously.',fontsize=9,color='#555555',va='top')
for ext in ['png','svg']:fig.savefig(ROOT/f'source_group_application.{ext}',dpi=160,bbox_inches='tight',facecolor='white')
