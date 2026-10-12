from pathlib import Path
import json,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

JOB=Path(__file__).resolve().parent.parent
OUT=JOB/'release/figures'
Q=json.loads((JOB/'qa/nan_guard_component_summary.json').read_text('utf-8'))
M=json.loads((JOB/'qa/main_nan_result.json').read_text('utf-8'))
assert Q['checks_passed']==1917 and Q['faulty_storage_cases']==32 and Q['normal_storage_cases']==56
assert len(Q['expiry_records'])==12 and all(x['baseline_storage_calls']==1 and x['candidate_storage_calls']==0 for x in Q['expiry_records'])
assert Q['expiry_fault_cases']==16 and Q['expiry_normal_pairs']==40
assert M['status']=='pass' and M['total_main_runs']==120 and M['conditions']==18 and M['compared_payload_pairs']==760
assert M['actual_checkpoint_read_runs']==6 and all(x['main_runs']==40 for x in M['by_variant'].values())

# humanize-kit:humanizer, Embedded mode: draft, audit, final.
# These text-only edits retain every result, denominator and validation scope.
CAPTION_DRAFTS={
 'nan_residual_storage':'The two residual storage methods were tested with 32 injected calls. The baseline produced 12 non-finite cell values, 8 indexing exceptions, and 12 writes to the wrong coordinates. The patch preserved all 32 destination grids, while 56 finite calls produced bit-identical float32 storage payloads.',
 'nan_early_expiry':'This diagram highlights where the guard is placed after vertical motion and sedimentation, ensuring that invalid state is stopped before the transient expiry branch. It prevented storage calls in all 16 injected expiry cases; 40 finite baseline/candidate pairs kept identical float32 storage payloads. Earlier valid receptor contributions are retained, while the untracked remainder is discarded without redistribution.',
 'nan_validation_scope':'Validation was performed on three levels: actual DLL methods, compiled production blocks, and a synthetic Main suite. The Main suite ran 18 conditions across baseline and two independent patches, for 120 executions and 760 identical payload pairs. Six executions read existing checkpoints. The counts include the shared baseline.'}
CAPTION_AUDIT={
 'nan_residual_storage':'Tighten repeated testing phrasing; retain two actual methods, 32 injected calls, all three baseline outcomes, 32 preserved grids and 56 finite equal-payload calls. No incidence or accuracy claim.',
 'nan_early_expiry':'Remove the framing verb highlights and the loose ensuring rider. State the guard position and tested outcomes directly. Keep 16 candidate cases distinct from the 12 recorded baseline calls; retain 40 normal pairs and the loss policy.',
 'nan_validation_scope':'Replace method narration with concrete test scope. Keep 18/120/760/6 and shared-baseline counting. Separate actual DLL calls from extracted blocks; do not imply a full Main injected-fault test.'}
CAPTIONS={
 'nan_residual_storage':'Across two actual residual storage methods, 32 injected calls produced 12 non-finite cell values, 8 indexing exceptions and 12 wrong-coordinate writes in the baseline. The patch preserved all 32 destination grids. In 56 finite calls, baseline and patched float32 storage payloads were bit-identical.',
 'nan_early_expiry':'The guard runs after vertical motion and sedimentation, before the transient expiry branch. It prevented storage calls in all 16 injected expiry cases; 40 finite baseline/candidate pairs kept identical float32 storage payloads. Earlier valid receptor contributions are retained. The untracked remainder is discarded without redistribution.',
 'nan_validation_scope':'Component checks used actual DLL methods and compiled production blocks. The separate synthetic Main suite ran 18 conditions across baseline and two independent patches, for 120 executions and 760 identical payload pairs. Six executions read existing checkpoints. Counts include the shared baseline.'}

C={'ink':'#243444','muted':'#5C6975','line':'#D5DDE4','bg':'#F5F7F9','blue':'#0072B2','green':'#008B66','orange':'#E69F00','red':'#D55E00'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':14,'text.color':C['ink'],'axes.labelcolor':C['ink'],'svg.fonttype':'none'})

def canvas(title,subtitle,height=8):
 fig=plt.figure(figsize=(15,height),facecolor='white');ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
 ax.text(.055,.955,title,fontsize=25,weight='bold',va='top')
 ax.text(.055,.893,subtitle,fontsize=13,color=C['muted'],va='top')
 return fig,ax

def rect(ax,x,y,w,h,fill='white',edge=None,radius=.009):
 p=FancyBboxPatch((x,y),w,h,boxstyle=f'round,pad=0.004,rounding_size={radius}',facecolor=fill,edgecolor=edge or C['line'],linewidth=1)
 ax.add_patch(p);return p

def save(fig,name):
    OUT.mkdir(parents=True,exist_ok=True)
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    width,height=fig.canvas.get_width_height()
    for axes in fig.axes:
        for text in axes.texts:
            if not text.get_text(): continue
            bounds=text.get_window_extent(renderer)
            if bounds.x0<2 or bounds.y0<2 or bounds.x1>width-2 or bounds.y1>height-2:
                raise ValueError('Text exceeds figure canvas: '+text.get_text())
    fig.savefig(OUT/(name+'.png'),dpi=150,facecolor='white')
    fig.savefig(OUT/(name+'.svg'),facecolor='white')
    plt.close(fig)
    print('[SAVE]',name+'.png')

def storage_figure():
 faults=Q['fault_records'];nonfinite=sum(x['baseline_nonfinite'] for x in faults);exceptions=sum(bool(x['baseline_exception']) for x in faults)
 wrong=sum(x['baseline_grid_changed'] and not x['baseline_nonfinite'] and not x['baseline_exception'] for x in faults)
 assert (nonfinite,exceptions,wrong)==(12,8,12) and all(x['candidate_cell_unchanged'] for x in faults)
 fig,ax=canvas('Residual storage preserves the grid when a write is invalid','Actual DLL methods | 32 injected calls across both storage paths')
 for x in [.055,.525]:rect(ax,x,.21,.42,.61,C['bg'])
 ax.text(.08,.79,'Baseline',fontsize=20,weight='bold');ax.text(.55,.79,'Storage patch',fontsize=20,weight='bold')
 ax.text(.08,.728,'Invalid input reaches indexing or addition',fontsize=13)
 ax.text(.55,.728,'Validate position, increment and locked sum',fontsize=13)
 width=.365;barY=.575;barH=.095;start=.08
 for value,color in [(nonfinite,C['red']),(exceptions,C['blue']),(wrong,C['orange'])]:
  rect(ax,start,barY,width*value/32,barH,color,color,radius=.002)
  ax.text(start+width*value/64,barY+barH/2,str(value),ha='center',va='center',fontsize=22,weight='bold',color='white' if color!=C['orange'] else C['ink'])
  start+=width*value/32
 rect(ax,.55,barY,width,barH,C['green'],C['green'],radius=.002)
 ax.text(.55+width/2,barY+barH/2,'32',ha='center',va='center',fontsize=23,weight='bold',color='white')
 labels=[('Non-finite cell value',nonfinite,C['red']),('IndexOutOfRangeException',exceptions,C['blue']),('Write at the wrong coordinates',wrong,C['orange'])]
 for n,(label,value,color) in enumerate(labels):
  y=.495-n*.084;ax.plot([.08,.10],[y,y],color=color,linewidth=8,solid_capstyle='butt')
  ax.text(.115,y,label,fontsize=13,va='center');ax.text(.443,y,str(value),fontsize=16,ha='right',va='center',weight='bold')
 ax.text(.55,.495,'All destination grids unchanged',fontsize=16,weight='bold',va='center')
 ax.text(.55,.407,'32 rejected calls returned without\nchanging the stored concentration.',fontsize=14,va='center',linespacing=1.5)
 rect(ax,.055,.105,.89,.065,'#E9F3F8',edge='#C4DFED')
 ax.text(.08,.137,'56 finite calls: identical float32 storage payloads',fontsize=16,weight='bold',va='center')
 ax.text(.055,.062,'Injected component cases establish rejection behavior. They do not measure failure incidence in model runs.',fontsize=12,color=C['muted'])
 save(fig,'nan_residual_storage')

def expiry_figure():
 fig,ax=canvas('Check the updated height before transient expiry can store it','Extracted production sedimentation and expiry code | Storage calls use the unpatched DLL',height=8.6)
 for x in [.055,.525]:rect(ax,x,.185,.42,.64,C['bg'])
 ax.text(.08,.794,'Baseline',fontsize=20,weight='bold');ax.text(.55,.794,'State patch',fontsize=20,weight='bold')
 def node(x,y,w,h,text,fill='white',fontsize=14):
  rect(ax,x,y,w,h,fill)
  ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=fontsize,linespacing=1.38)
 def arrow(a,b,color=C['muted']):ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'-|>','color':color,'linewidth':1.8,'mutation_scale':15})
 node(.08,.64,.37,.10,'Vertical motion and sedimentation\nupdate the particle height')
 node(.55,.64,.37,.10,'Vertical motion and sedimentation\nupdate the particle height')
 node(.08,.465,.37,.10,'Transient expiry branch\nselects a residual storage call')
 node(.55,.465,.37,.10,'Check x, y, z, mass and dt\nbefore the expiry branch',fill='#E9F3F8')
 arrow((.265,.635),(.265,.57));arrow((.735,.635),(.735,.57))
 node(.08,.30,.37,.10,'The storage call receives\nthe non-finite height',fill='#FBECE7')
 arrow((.265,.46),(.265,.405),C['red'])
 node(.55,.293,.176,.108,'Non-finite state\nREMOVE_PARTICLE\nSkip storage',fill='#FBECE7',fontsize=13)
 node(.744,.293,.176,.108,'Finite state\nExisting expiry\nand storage',fill='#EAF5F0',fontsize=13)
 arrow((.68,.46),(.638,.406),C['red']);arrow((.79,.46),(.832,.406),C['green'])
 ax.text(.265,.235,'12 tested NaN/Inf height cases\ncalled unpatched storage',ha='center',fontsize=13,linespacing=1.45)
 ax.text(.735,.235,'16 injected cases: 0 storage calls\n40 finite pairs: identical float32 grids',ha='center',fontsize=13,linespacing=1.45)
 rect(ax,.055,.075,.89,.074,'#E9F3F8',edge='#C4DFED')
 ax.text(.08,.112,'Earlier valid receptor contributions remain. The untracked remainder is discarded without redistribution.',fontsize=13,va='center')
 ax.text(.055,.035,'The 16 candidate cases include 12 non-finite heights and 4 finite arithmetic overflows. No full Main fault injection.',fontsize=11.5,color=C['muted'])
 save(fig,'nan_early_expiry')

def validation_figure():
 fig,ax=canvas('NaNGuard checks: injected faults and normal Main runs','Frozen source | Actual DLL calls, compiled production blocks and a separate synthetic Main suite',height=8)
 xs=[.055,.253,.647,.945];top=.81;headH=.066;rowH=.155
 rect(ax,.055,top-headH,.89,headH,'#E9F3F8',edge='#C4DFED')
 for x,title in zip(xs[:3],['Execution scope','Cases exercised','Observed result']):ax.text(x+.013,top-headH/2,title,fontsize=15,weight='bold',va='center')
 rows=[
  ('Actual DLL methods','20 initial driver cases\n56 finite + 32 injected storage calls\nAtomic counters with 1 and 2 workers','Invalid initial states rejected\nFinite storage bits unchanged\nRejected writes preserve the grid'),
  ('Compiled production\nblocks','18 guard boundaries; prior receptor values\n14 decay/wet cases; 8 report cases\n16 expiry faults + 40 finite pairs','Expiry faults stop before storage\nEarlier receptor values retained\nZero counters produce no report'),
  ('Normal Main suite','18 conditions; 120 executions\n40 baseline + 40 state + 40 storage\n6 actual checkpoint-read executions','760 payload pairs identical\nNo guard reports on normal inputs\nBaseline/candidate restart matches')]
 for i,(scope,cases,result) in enumerate(rows):
  y=top-headH-(i+1)*rowH
  rect(ax,.055,y,.89,rowH,'white' if i%2==0 else C['bg'],radius=.001)
  ax.text(xs[0]+.013,y+rowH/2,scope,fontsize=14,weight='bold',va='center',linespacing=1.5)
  ax.text(xs[1]+.013,y+rowH/2,cases,fontsize=13,va='center',linespacing=1.65)
  ax.text(xs[2]+.013,y+rowH/2,result,fontsize=13,va='center',linespacing=1.65)
 rect(ax,.055,.16,.89,.065,'#EAF5F0',edge='#C4E3D4')
 ax.text(.08,.192,'1,917 component checks and 1,896 Main checks passed',fontsize=17,weight='bold',va='center')
 ax.text(.055,.098,'Main counts include the shared baseline and use controlled fixed-seed cases. Injected faults were component tests.',fontsize=12,color=C['muted'])
 ax.text(.055,.061,'Payload equality is a regression check; it does not establish field accuracy or full continuous/resumed state equality.',fontsize=12,color=C['muted'])
 save(fig,'nan_validation_scope')

if __name__=='__main__':
 storage_figure();expiry_figure();validation_figure()
 for name,text in CAPTIONS.items():print('[CAPTION]',name,text)
