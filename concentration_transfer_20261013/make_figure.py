from pathlib import Path
import argparse, csv, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,required=True)
args=parser.parse_args()
root=args.root
rows=list(csv.DictReader((root/'results/transfer_summary.csv').open(encoding='utf-8-sig')))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
fig=plt.figure(figsize=(12.6,7.8),facecolor='white')
fig.text(.065,.94,'Copy completed concentrations in parallel',fontsize=24,weight='bold',color='#203640')
fig.text(.065,.889,'Each column is independent: cast each double sum to float, then clear its accumulator.',fontsize=12,color='#526670')
fig.text(.065,.838,'One worker or fewer than 131,072 values: keep the serial loop.',fontsize=12,color='#526670')
for pos,(nx,label) in enumerate(((116,'116 × 84 × 9 × 108 values'),(230,'230 × 166 × 9 × 108 values'))):
    ax=fig.add_axes([.095+pos*.475,.29,.38,.46])
    selected=sorted([r for r in rows if int(r['nx'])==nx and int(r['slices'])==9],key=lambda r:int(r['workers']))
    before=np.array([float(r['baseline_median_ms']) for r in selected])
    after=np.array([float(r['candidate_median_ms']) for r in selected])
    x=np.arange(len(selected));w=.33
    b=ax.bar(x-w/2,before,w,color='#70828a',label='Serial transfer')
    c=ax.bar(x+w/2,after,w,color='#007f91',label='With size / worker check')
    ax.bar_label(b,fmt='%.2f',padding=4,fontsize=11)
    ax.bar_label(c,fmt='%.2f',padding=4,fontsize=11)
    ax.set_ylim(0,max(before.max(),after.max())*1.25)
    ax.set_xticks(x,[str(r['workers']) for r in selected])
    ax.set_xlabel('Workers',labelpad=10)
    ax.set_ylabel('Transfer time (ms)',labelpad=8)
    ax.set_title(label,fontsize=14,pad=20,weight='bold',loc='left')
    ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    ax.spines['left'].set_color('#b9c7cc');ax.spines['bottom'].set_color('#b9c7cc')
    if pos==0:fig.legend(handles=[b,c],labels=['Serial transfer','With size / worker check'],loc='lower left',bbox_to_anchor=(.075,.17),frameon=False,ncol=2)
fig.text(.065,.115,'Warm compiled transfer method; medians of 13 recorded batches. Lower is faster.',fontsize=11,color='#526670')
fig.text(.065,.073,'Exact cast/reset checks passed, including zero slices, NaN, infinity and signed zero.',fontsize=11,color='#526670')
fig.text(.065,.035,'Six final-code Main runs retained byte-identical concentration payloads.',fontsize=11,color='#526670')
out=root/'figures';out.mkdir(exist_ok=True)
for ext in ('png','svg'):
    fig.savefig(out/f'parallel_transfer.{ext}',dpi=180,facecolor='white')
plt.close(fig)
print('[SAVE] parallel_transfer.png / parallel_transfer.svg')
