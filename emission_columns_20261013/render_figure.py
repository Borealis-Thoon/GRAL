from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
d=json.loads((R/'figure_data.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold'})
before='#B36A45';after='#23756A';ink='#243444'
fig=plt.figure(figsize=(12,6.8),layout='none');fig.patch.set_facecolor('white')
if d['topic']=='progress_interval':
    fig.text(.055,.94,'A zero progress interval can leave particles unprocessed',fontsize=20,weight='bold',color=ink)
    fig.text(.055,.883,'Fixed seeds, six particles. The one-line guard keeps the interval at one or more.',fontsize=12,color='#536575')
    axes=[fig.add_axes([.07,.25,.40,.52]),fig.add_axes([.57,.25,.38,.52])]
    x=np.arange(3);width=.34
    for ax,field,title,label in zip(axes,['visits','logged_release_g'],['Actual driver calls','Full-engine source release'],['Particles processed','Logged release (g)']):
        for v,color,shift,lab in [('baseline',before,-width/2,'Before'),('candidate',after,width/2,'After')]:
            vals=[next(r[field] for r in d['rows'] if r['workers']==w and r['variant']==v) for w in [1,4,24]]
            bars=ax.bar(x+shift,vals,width,color=color,label=lab,zorder=3)
            ax.bar_label(bars,labels=[f'{v:g}' if field=='visits' else f'{v:.2f}' for v in vals],padding=5,fontsize=11)
        ax.set_xticks(x,['1 worker','4 workers','24 workers']);ax.set_title(title,loc='left',pad=18);ax.set_ylabel(label);ax.grid(axis='y',alpha=.18,zorder=0)
    axes[0].set_ylim(0,7.6);axes[0].set_yticks([0,2,4,6]);axes[0].legend(frameon=False,loc='upper left',ncol=2)
    axes[1].set_ylim(0,10.6);expected=d['rows'][0]['expected_release_g'];axes[1].axhline(expected,color='#536575',ls=':',lw=1.5)
    axes[1].text(.0,1.03,'Expected: 1 kg/h for 30 s = 8.333 g',transform=axes[1].transAxes,color='#536575',fontsize=10)
    fig.text(.055,.125,'Before: index % 0 interrupts each worker after its first particle. The existing catch hides the exception.',fontsize=11,color=ink)
    fig.text(.055,.075,'After: all six particles are processed. Values shown are medians of three repeats; release values come from the engine log.',fontsize=10,color='#536575')
else:
    fig.text(.055,.94,'An unused source-group column can stop emission input',fontsize=20,weight='bold',color=ink)
    fig.text(.055,.883,'Selected group: 1. Input header: group 2, then group 1. Group 2 should be ignored.',fontsize=12,color='#536575')
    ax=fig.add_axes([.085,.24,.84,.51]);x=np.arange(3);width=.34
    for v,color,shift,lab in [('baseline',before,-width/2,'Before'),('candidate',after,width/2,'After')]:
        vals=[r['actual'] for r in d['rows'] if r['variant']==v]
        bars=ax.bar(x+shift,vals,width,color=color,label=lab,zorder=3);ax.bar_label(bars,labels=[f'{v:g}' for v in vals],padding=5,fontsize=13)
    expected=[r['expected'] for r in d['rows'] if r['variant']=='candidate']
    ax.scatter(x,expected,marker='_',s=1000,color=ink,zorder=4,label='Input factor')
    ax.set_xticks(x,['Row 1','Row 2','Row 3']);ax.set_ylabel('Emission factor for selected group 1');ax.set_ylim(0,2.65);ax.grid(axis='y',alpha=.18,zorder=0);ax.legend(frameon=False,ncol=3,loc='upper left')
    fig.text(.055,.13,'Before: the unused column triggers an invalid index; later rows retain zero factors.',fontsize=11,color=ink)
    fig.text(.055,.078,'After: unused columns are skipped and all selected factors are read. The mean array follows the input column count.',fontsize=11,color=ink)
(R/'figures').mkdir(exist_ok=True)
for ext in ['png','svg']:fig.savefig(R/'figures'/(d['topic']+'.'+ext),dpi=180,facecolor='white')
print('[FIGURE]',d['topic'])
