from pathlib import Path
import json, os
os.environ['MPLCONFIGDIR']=str(Path(__file__).resolve().parent.parent/'figure_cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
D=json.loads((ROOT/'figure_data.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','savefig.facecolor':'white'})
C=['#b97b3c','#167f7a']
def save(fig,name):
 for ext in ['png','svg']:fig.savefig(ROOT/'figures'/f'{name}.{ext}',dpi=170,bbox_inches='tight')
 plt.close(fig)
def bars(ax,values,labels,ylim,ylabel):
 b=ax.bar(labels,values,color=C,width=.53);ax.set_ylim(0,ylim);ax.set_ylabel(ylabel);ax.yaxis.grid(True,color='#dddddd',alpha=.55);ax.set_axisbelow(True)
 for item,v in zip(b,values):ax.text(item.get_x()+item.get_width()/2,v+ylim*.035,f'{v:,}',ha='center',fontweight='bold',fontsize=17)
r=D['residual'];fig,axs=plt.subplots(1,2,figsize=(11,5.7));fig.subplots_adjust(left=.08,right=.96,top=.77,bottom=.25,wspace=.36)
fig.suptitle('Stop planning when every residual entry has one particle',x=.04,ha='left',fontsize=18,fontweight='bold')
fig.text(.04,.87,f"Planner fixture: {r['eligible']} eligible entries, target {r['target']}, {r['workers']} workers",fontsize=12,color='#444444')
bars(axs[0],[r['before_scans'],r['after_scans']],['Previous #63','Revised #63'],7.2,'Full field scans');axs[0].set_title('Less repeated planning',loc='left',fontweight='bold',pad=15)
bars(axs[1],[r['before_releases'],r['after_releases']],['Previous #63','Revised #63'],360,'Residual particle releases');axs[1].set_title('The release count stays the same',loc='left',fontweight='bold',pad=15)
fig.text(.04,.11,'225 planner cases: every split count unchanged.\n16 Main runs: all 140 paired concentration payloads identical.',fontsize=12)
save(fig,'pr63_floor_exit')
r=D['precision'];fig,axs=plt.subplots(1,2,figsize=(11,5.7));fig.subplots_adjust(left=.09,right=.96,top=.73,bottom=.30,wspace=.42)
fig.suptitle('Double accumulation: measured repeatability and memory',x=.035,ha='left',fontsize=18,fontweight='bold')
axs[0].set_title('100,000 particles, 4 workers\nFive runs with the same seed',loc='left',fontweight='bold',pad=16)
bars(axs[0],[r['before_max_changed_cells'],r['after_max_changed_cells']],['V2701','#64'],18,'Maximum changed cells out of 7,200');axs[0].set_yticks([0,5,10,15])
mem=r['memory'];v=[x['allocated_bytes']/1048576 for x in mem];labels=['500 m\n114 × 82','250 m\n228 × 164'];bars(axs[1],v,labels,360,'Additional allocated memory (MiB)')
for item in axs[1].patches:item.set_color('#597184')
for txt in list(axs[1].texts):txt.remove()
for i,val in enumerate(v):axs[1].text(i,val+12,f'{val:.2f} MiB',ha='center',fontweight='bold',fontsize=14)
axs[1].set_title('Exact double-buffer allocation\n9 output slices, 108 source groups',loc='left',fontweight='bold',pad=16)
fig.text(.035,.075,f"Each repeat is compared with its first run. Largest baseline cell difference: {r['max_relative_cell_difference_percent']:.6f}%.\nMemory measurements include the numeric payload and array overhead.",fontsize=11)
save(fig,'pr64_precision_cost')
print('[SAVE] review figures')
