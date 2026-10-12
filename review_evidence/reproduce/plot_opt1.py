from pathlib import Path
import os,sys,json,hashlib
J=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(J/'cache/opt1_figures'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import numpy as np
from matplotlib.patches import FancyBboxPatch
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':14,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','svg.fonttype':'none','figure.facecolor':'white','axes.facecolor':'white'})
OUT=J/'release/figures';OUT.mkdir(parents=True,exist_ok=True)
QA=J/'qa'
base=json.loads((QA/'opt1_benchmark.json').read_text());paired=json.loads((QA/'opt1_paired_benchmark.json').read_text());actual=json.loads((QA/'opt1_actual_cache_hits.json').read_text())
BLUE='#007D96';GRAY='#5F7080';INK='#20333F';ORANGE='#C66A24'
texts=[];files=[]
def save(fig,name):
    fig.canvas.draw();width,height=fig.canvas.get_width_height();bad=[]
    for t in fig.findobj(matplotlib.text.Text):
        if not t.get_text() or not t.get_visible():continue
        b=t.get_window_extent(fig.canvas.get_renderer())
        if b.width>0 and b.height>0 and (b.x0<-1 or b.y0<-1 or b.x1>width+1 or b.y1>height+1):bad.append({'text':t.get_text(),'bbox':[b.x0,b.y0,b.x1,b.y1]})
    assert not bad,bad
    for ext in ['png','svg']:
        p=OUT/(name+'.'+ext);fig.savefig(p,dpi=150,bbox_inches=None,metadata={'Title':name});files.append({'path':str(p.relative_to(J)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size})
    texts.append({'figure':name,'canvas_pixels':[width,height],'text_within_canvas':True,'outside_text':bad})
    plt.close(fig)

fig=plt.figure(figsize=(15,8.8),dpi=150)
fig.text(.045,.943,'Bounded stack storage removes small per-particle heap allocations',fontsize=24,fontweight='bold',color=INK)
fig.text(.045,.895,'Actual compiled Calculate entry; median heap bytes per call across seven rounds',fontsize=15,color=GRAY)
for x,title,desc,edge in [(.075,'Baseline','Heap array for each eligible particle',GRAY),(.53,'Patch','Stack for NS <= 512; heap above 512',BLUE)]:
    box=FancyBboxPatch((x,.745),.395,.10,boxstyle='round,pad=0.01,rounding_size=0.008',transform=fig.transFigure,facecolor='#F3F7F8',edgecolor=edge,linewidth=1.7);fig.add_artist(box)
    fig.text(x+.017,.806,title,fontsize=17,fontweight='bold',color=edge);fig.text(x+.017,.771,desc,fontsize=14,color=INK)
fig.add_artist(matplotlib.patches.FancyArrowPatch((.48,.795),(.518,.795),transform=fig.transFigure,arrowstyle='->',mutation_scale=20,color=INK,linewidth=1.8))
rows={r['ns']:r for r in base['stack_entries']}
for bounds,nslist,ymax,title in [([.09,.25,.365,.395],[1,9],82,'Common slice counts'),([.57,.25,.365,.395],[512,513],2550,'Stack limit boundary')]:
    ax=fig.add_axes(bounds);x=np.arange(2);w=.33
    old=[rows[n]['baseline_bytes_per_entry'] for n in nslist];new=[rows[n]['candidate_bytes_per_entry'] for n in nslist]
    bars1=ax.bar(x-w/2,old,w,color=GRAY,label='Baseline');bars2=ax.bar(x+w/2,new,w,color=BLUE,label='Patch')
    for bars in [bars1,bars2]:
        for b in bars:
            y=b.get_height();ax.annotate(f'{y:,.0f}',(b.get_x()+b.get_width()/2,y),xytext=(0,7 if y else 5),textcoords='offset points',ha='center',fontsize=18,fontweight='bold',color=b.get_facecolor())
    ax.set_ylim(0,ymax);ax.set_xticks(x,[f'NS = {n}' for n in nslist]);ax.tick_params(axis='x',labelsize=16);ax.tick_params(axis='y',labelsize=13)
    ax.set_ylabel('Heap bytes per entry',fontsize=14);ax.set_title(title,fontsize=17,loc='left',pad=15);ax.yaxis.grid(True,color='#DAE1E5',linewidth=.7);ax.set_axisbelow(True)
    if nslist==[1,9]:ax.legend(loc='upper left',frameon=False,fontsize=14,ncol=2,bbox_to_anchor=(0,1.015))
fig.text(.09,.185,'512 integer slots use at most 2 KiB of stack storage.',fontsize=15,color=INK)
fig.text(.57,.185,'The 513-slice case keeps the existing heap fallback.',fontsize=15,color=INK)
fig.text(.045,.101,'The measured calls reached the slice declaration, then removed an out-of-domain particle.',fontsize=14,color=GRAY)
fig.text(.045,.058,'These are entry-point allocation measurements. Complete simulation runtime was not measured.',fontsize=14,color=GRAY)
save(fig,'opt1_slice_stack_allocation')

fig=plt.figure(figsize=(15,11.6),dpi=150)
fig.text(.045,.95,'Lookup gains depend on repeated particle heights',fontsize=24,fontweight='bold',color=INK)
fig.text(.045,.916,'Same finite height: reuse the previous layer. Changed height: run the existing binary search.',fontsize=15,color=GRAY)
norm=colors.TwoSlopeNorm(vmin=-85,vcenter=0,vmax=35)
cmap=colors.LinearSegmentedColormap.from_list('time_change',[BLUE,'#FFFFFF',ORANGE])
leftrows=[(n,l) for n in [1,7,8,16,162] for l in [8,64,256]]
rightrows=[(n,l) for n in [1,39,162] for l in [8,64,256]]
left=np.array([[(1/next(r['baseline_over_candidate'] for r in base['vertical_lookup'] if r['nkk']==n and r['lookups_per_particle']==l and r['workload']==k)-1)*100 for k in ['same_height','same_layer','large_jumps']] for n,l in leftrows])
right=np.array([[next(r['candidate_runtime_percent_change'] for r in paired['records'] if r['nkk']==n and r['lookups_per_particle']==l and r['workload']==k) for k in ['paired_same_layer','paired_large_jumps']] for n,l in rightrows])
def matrix(bounds,arr,rows,columns):
    ax=fig.add_axes(bounds);im=ax.imshow(arr,norm=norm,cmap=cmap,aspect='auto',interpolation='nearest')
    ax.set_xticks(np.arange(len(columns)),columns);ax.set_yticks(np.arange(len(rows)),[f'{n} / {l}' for n,l in rows]);ax.tick_params(axis='x',top=True,labeltop=True,bottom=False,labelbottom=False,length=0,pad=9,labelsize=13);ax.tick_params(axis='y',length=0,pad=8,labelsize=13)
    ax.set_xticks(np.arange(-.5,arr.shape[1],1),minor=True);ax.set_yticks(np.arange(-.5,arr.shape[0],1),minor=True);ax.grid(which='minor',color='#CAD5DA',linewidth=.65);ax.tick_params(which='minor',bottom=False,left=False)
    for spine in ax.spines.values():spine.set_visible(False)
    for i in range(arr.shape[0]):
        for k in range(arr.shape[1]):ax.text(k,i,f'{arr[i,k]:+.1f}',ha='center',va='center',fontsize=14,color='white' if arr[i,k]<-55 or arr[i,k]>25 else INK,fontweight='bold')
    return im
im=matrix([.14,.255,.43,.50],left,leftrows,['Same height\none initial miss','Moving in layer\n0% cache hits','Large jumps\n0% cache hits'])
matrix([.71,.465,.235,.29],right,rightrows,['Paired movement\n50% cache hits','Paired jumps\n50% cache hits'])
fig.text(.14,.855,'Original benchmarks: 45 cases',fontsize=18,fontweight='bold',color=INK)
fig.text(.71,.855,'Paired benchmarks: 18 cases',fontsize=18,fontweight='bold',color=INK)
fig.text(.048,.810,'NKK / calls\nper particle',fontsize=12.5,color=GRAY)
fig.text(.605,.810,'NKK / calls\nper particle',fontsize=12.5,color=GRAY)
for x,y,w,h in [(.665,.223,.29,.18)]:
    box=FancyBboxPatch((x,y),w,h,transform=fig.transFigure,boxstyle='round,pad=0.014,rounding_size=.008',facecolor='#F2F6F7',edgecolor='#A5B9C2',linewidth=1.1);fig.add_artist(box)
fig.text(.682,.371,'Observed reuse in Main',fontsize=17,fontweight='bold',color=INK)
fig.text(.682,.34,f'{actual["hits"]:,} / {actual["calls"]:,} calls',fontsize=15,color=INK)
fig.text(.682,.308,'About 50% reused the prior result',fontsize=14,color=BLUE)
fig.text(.682,.275,'Two synthetic terrain projects, NKK = 39',fontsize=12.5,color=GRAY)
fig.text(.682,.247,'4 instrumented runs; 146 equal payload pairs',fontsize=12,color=GRAY)
cax=fig.add_axes([.14,.177,.43,.018]);cb=fig.colorbar(im,cax=cax,orientation='horizontal',ticks=[-80,-40,0,20]);cb.ax.tick_params(labelsize=12)
cb.set_label('Change in lookup time (%): below zero is faster',fontsize=14,labelpad=7)
fig.text(.14,.217,'All constant-height cases improved; 29 of 30 changing-height cases slowed.',fontsize=12.4,color=GRAY)
fig.text(.665,.433,'Paired lookup gain: 1.148 to 1.585 times.',fontsize=12.5,color=BLUE)
fig.text(.045,.098,'Seven alternating timing rounds, with a fresh cache per particle. Paired sequences are synthetic;',fontsize=14,color=GRAY)
fig.text(.045,.071,'they give 50% cache hits and do not replay Main height traces. Main counters measure reuse, not runtime.',fontsize=14,color=GRAY)
fig.text(.045,.043,'The heatmaps report lookup cost. Complete GRAL speedup was not measured.',fontsize=14,color=GRAY)
save(fig,'opt1_vertical_lookup_tradeoffs')
inputs=[]
for name in ['opt1_benchmark.json','opt1_paired_benchmark.json','opt1_actual_cache_hits.json','opt1_paired_benchmark_captions.json','opt1_paired_benchmark_caption_audit.json']:
    p=QA/name;inputs.append({'path':str(p.relative_to(J)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(QA/'opt1_paired_benchmark_figure_qa.json').write_text(json.dumps({'status':'pass','files':files,'canvas_checks':texts,'input_hashes':inputs,'paired_scope':'Synthetic height pairs, not a Main height trace replay','slower_original_conditions_shown':29,'full_model_speedup_claim':False,'visual_inspection':'pending view_image'},indent=2)+'\n')
print('[SAVED] opt1_figures PNG2 SVG2 width2250')
