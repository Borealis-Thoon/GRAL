from pathlib import Path
import json,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
R=Path(__file__).resolve().parent;data=json.loads((R/'results/summary.json').read_text());rows=data['summaries']
order=['current','reviewed','combined_off','combined_on'];names=['Current upstream','Reviewed PRs','Combined, buffers off','Combined, buffers on'];colors=['#8A939E','#3B78A0','#D69036','#2F8065']
labels={
 'concentrated_100k_w4':('100,000 particles · 4 workers','Stable air, concentrated point sources'),
 'concentrated_1m_unstable_w24':('1,000,000 particles · 24 workers','Unstable air, concentrated point sources'),
 'wide_9slice_8sg_100k_w24':('100,000 particles · 24 workers','120 × 120 cells, 9 slices, 8 source groups'),
 'small_3k_w1':('3,000 particles · 1 worker','Small field; worker buffers fall back to shared sums')}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,'axes.spines.bottom':False,'svg.fonttype':'none'})
fig,axs=plt.subplots(2,2,figsize=(14.8,10.8));fig.subplots_adjust(top=.83,bottom=.23,left=.17,right=.98,wspace=.53,hspace=.94)
fig.text(.025,.967,'Combined changes: benefit depends on workload',fontsize=22,weight='bold',color='#243444')
fig.text(.025,.929,'Elapsed time per run, including startup and output. Bars show medians; whiskers show the range of five runs.',fontsize=11.8,color='#46586B')
for ax,c in zip(axs.flat,data['conditions']):
 rr={r['variant']:r for r in rows if r['case']==c['id']};t=[rr[v]['median_wall_s'] for v in order];lo=[t[i]-rr[v]['min_wall_s'] for i,v in enumerate(order)];hi=[rr[v]['max_wall_s']-t[i] for i,v in enumerate(order)]
 y=np.arange(4);ax.barh(y,t,color=colors,height=.56,zorder=2);ax.errorbar(t,y,xerr=[lo,hi],fmt='none',ecolor='#263644',capsize=3,lw=1,zorder=3);ax.invert_yaxis();ax.set_yticks(y,names,fontsize=10);ax.tick_params(axis='y',length=0);ax.set_xlabel('Elapsed time (seconds)',fontsize=10);limit=max(rr[v]['max_wall_s'] for v in order);ax.set_xlim(0,limit*1.25);ax.grid(axis='x',alpha=.17,zorder=0)
 title,subtitle=labels[c['id']];ax.text(0,1.20,title,transform=ax.transAxes,fontsize=13,weight='bold',color='#243444');ax.text(0,1.10,subtitle,transform=ax.transAxes,fontsize=9.3,color='#586879')
 for i,v in enumerate(order):ax.text(rr[v]['max_wall_s']+limit*.035,i,f'{t[i]:.3f}',va='center',fontsize=10)
 delta=(t[3]/t[0]-1)*100;ws0=rr['current']['median_peak_working_bytes']/2**20;ws1=rr['combined_on']['median_peak_working_bytes']/2**20
 change=f'{abs(delta):.1f}% '+('shorter' if delta<0 else 'longer');ax.text(0,-.31,f'Buffers on vs upstream: {change}',transform=ax.transAxes,fontsize=11,weight='bold',color='#2F8065' if delta<0 else '#9B6330');ax.text(0,-.43,f'Median peak working set: {ws0:.1f} → {ws1:.1f} MiB',transform=ax.transAxes,fontsize=10,color='#46586B')
fig.text(.025,.073,'Reviewed PRs: #64, #66–#70. Combined adds #71 (transfer), #72 (variance reuse) and #73 (optional worker buffers).',fontsize=10,color='#46586B')
fig.text(.025,.047,'All reviewed and combined concentration files were byte-identical across variants and repeats in these four fields.',fontsize=10,color='#46586B')
fig.text(.025,.021,'80 synthetic stationary runs · AMD Ryzen 9 9950X3D · Windows 11 · current upstream 891225b2',fontsize=9,color='#657587')
(R/'figures').mkdir(exist_ok=True)
for ext in ['png','svg']:fig.savefig(R/'figures'/('integration_tradeoffs.'+ext),dpi=160,facecolor='white')
plt.close(fig)
