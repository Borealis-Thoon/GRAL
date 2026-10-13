from pathlib import Path
import json,re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
s=json.loads((ROOT/'results/performance.json').read_text())
labels=['100,000 particles · 4 workers','100,000 particles · 24 workers','1,000,000 particles · 24 workers','100,000 particles · 24 workers\n120 × 120 grid · 9 heights']
variants=['f64','off','on'];colors=['#798390','#aec0d0','#147d92']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titleweight':'bold','axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,2,figsize=(13.8,10.5));fig.subplots_adjust(top=.84,bottom=.23,hspace=1.05,wspace=.23)
fig.suptitle('Worker concentration buffers: time saved and memory used',fontsize=21,x=.055,ha='left',y=.975)
fig.text(.055,.92,'Each worker accumulates locally; the sums are merged after the particle loop. The option is off by default.',fontsize=11,color='#485564')
for idx,(ax,c) in enumerate(zip(axes.flat,s['conditions'])):
 rows={r['variant']:r for r in s['summaries'] if r['case']==c['id']};med=[rows[v]['median_s'] for v in variants];low=[rows[v]['min_s'] for v in variants];high=[rows[v]['max_s'] for v in variants]
 ax.bar(range(3),med,width=.52,color=colors,zorder=2)
 ax.errorbar(range(3),med,yerr=[[m-l for m,l in zip(med,low)],[h-m for h,m in zip(high,med)]],fmt='none',color='#293742',capsize=5,lw=1.3,zorder=3)
 for x,m,h in zip(range(3),med,high):ax.text(x,h+max(high)*.055,f'{m:.3f} s',ha='center',va='bottom',fontweight='bold',fontsize=11)
 ax.set_xticks(range(3),['#64 base','Candidate\nOFF','Candidate\nON']);ax.set_ylim(0,max(high)*1.32);ax.set_ylabel('Whole-process time (s)');ax.set_title(labels[idx],loc='left',fontsize=13,pad=14);ax.grid(axis='y',alpha=.18,zorder=0);ax.set_axisbelow(True)
 log=next(r['buffer_log'][0] for r in s['records'] if r['case']==c['id'] and r['variant']=='on');payload=int(re.search(r'reserved=(\d+)',log)[1])/2**20
 saving=(1-med[2]/med[0])*100;rss=f"{rows['f64']['peak_working_set']/2**20:.1f} → {rows['on']['peak_working_set']/2**20:.1f} MiB"
 ax.text(.02,-.33,f'{saving:.1f}% less time vs base  |  buffer payload {payload:.3f} MiB\nPeak working set: {rss}',transform=ax.transAxes,fontsize=10.5,linespacing=1.6,color='#2e4b59',va='top')
fig.text(.055,.057,'Bars: median of 5 interleaved runs. Whiskers: min–max. Fixed RNG seeds; synthetic fields; startup and output included.',fontsize=10,color='#4d5863')
fig.text(.055,.029,'All concentration payloads matched across these 60 runs. Enabled buffers change addition grouping; the storage cap is 256 MiB of elements.',fontsize=10,color='#4d5863')
for ext in ['png','svg']:fig.savefig(ROOT/f'worker_buffers_tradeoff.{ext}',dpi=170,facecolor='white')
print('[FIGURE] worker_buffers_tradeoff.png/svg')