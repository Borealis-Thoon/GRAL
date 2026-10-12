from pathlib import Path
import os, sys, json, hashlib, shutil
import argparse
parser=argparse.ArgumentParser(description="Render OPT1 summary figures from published measurements.")
parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parent)
args=parser.parse_args()
J=args.root.resolve()
os.environ.setdefault("MPLCONFIGDIR",str(J/".matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":16,"svg.fonttype":"none","figure.facecolor":"white","axes.facecolor":"white"})
OUT=J/"figures";OUT.mkdir(parents=True,exist_ok=True)
inputs=J/"inputs"; inputs.mkdir(exist_ok=True)
manifest=[]
for p in sorted(inputs.glob("*.json")):
 manifest.append({"name":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
base=json.loads((inputs/"opt1_benchmark_summary.json").read_text())
pair=json.loads((inputs/"opt1_paired_benchmark_summary.json").read_text())
actual=json.loads((inputs/"opt1_actual_cache_hits.json").read_text())
INK="#20343D";GRAY="#647780";BLUE="#087E91";ORANGE="#BD641A";PALE="#EDF6F7"
qa={"status":"pending_visual_review","input_hashes":manifest,"source_edits":0,"new_model_runs":0,"files":[],"figures":[]}
def label(fig,x,y,s,size=16,color=INK,weight="normal",ha="left"):
 return fig.text(x,y,s,fontsize=size,color=color,fontweight=weight,ha=ha,va="center")
def box(fig,x,y,w,h,color=PALE,edge="#C4D5DA"):
 fig.add_artist(FancyBboxPatch((x,y),w,h,transform=fig.transFigure,boxstyle="round,pad=0.012,rounding_size=0.01",facecolor=color,edgecolor=edge,linewidth=1))
def save(fig,name):
 fig.canvas.draw(); renderer=fig.canvas.get_renderer();w,h=fig.canvas.get_width_height();outside=[]
 for t in fig.findobj(matplotlib.text.Text):
  if not t.get_text() or not t.get_visible():continue
  b=t.get_window_extent(renderer)
  if b.width and b.height and (b.x0 < -1 or b.y0 < -1 or b.x1>w+1 or b.y1>h+1):outside.append(t.get_text())
 assert not outside,outside
 for ext in ["png","svg"]:
  p=OUT/(name+"."+ext);fig.savefig(p,dpi=150,metadata={"Title":name})
  qa["files"].append({"path":str(p.relative_to(J)).replace("\\","/"),"size":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
 qa["figures"].append({"name":name,"pixels":[w,h],"text_inside_canvas":True,"outside_text":outside})
 plt.close(fig)

fig=plt.figure(figsize=(15,8.5),dpi=150)
label(fig,.045,.943,"#68  Remove a small heap array from each particle call",25,weight="bold")
label(fig,.045,.885,"NS is the number of concentration slices. The slice-index calculations stay the same.",16,GRAY)
box(fig,.055,.665,.89,.155)
label(fig,.077,.771,"Example: NS = 9",17,GRAY)
label(fig,.077,.710,"64 bytes",32,GRAY,weight="bold")
label(fig,.255,.710,"of heap allocation",18,GRAY)
fig.add_artist(FancyArrowPatch((.505,.727),(.59,.727),transform=fig.transFigure,arrowstyle="->",mutation_scale=25,linewidth=2,color=INK))
label(fig,.625,.710,"0 bytes",32,BLUE,weight="bold")
label(fig,.802,.710,"on the heap",18,BLUE)
label(fig,.08,.597,"Slices (NS)",16,GRAY,weight="bold")
label(fig,.37,.597,"Before",16,GRAY,weight="bold")
label(fig,.55,.597,"After",16,BLUE,weight="bold")
label(fig,.73,.597,"Storage after patch",16,GRAY,weight="bold")
for i,r in enumerate(base["production_entry_allocation"]):
 y=.532-i*.082
 if i%2==0: box(fig,.065,y-.026,.86,.052,color="#F6F8F9",edge="#F6F8F9")
 n=r["ns"];a=r["baseline_bytes_per_entry"];b=r["candidate_bytes_per_entry"]
 label(fig,.08,y,f"{n}",21,weight="bold")
 label(fig,.37,y,f"{a:,} B",21,GRAY)
 label(fig,.55,y,f"{b:,} B",21,BLUE,weight="bold")
 label(fig,.73,y,"Stack" if n<=512 else "Heap fallback",18,BLUE if n<=512 else GRAY)
label(fig,.075,.199,"At most 2,048 bytes of stack payload for kko; larger arrays keep the heap path.",16,INK)
label(fig,.045,.125,"Measured heap bytes per call: actual compiled driver, 4,096 calls per condition, seven rounds.",14,GRAY)
label(fig,.045,.083,"Each call reached the declaration and then removed an out-of-domain particle.",14,GRAY)
label(fig,.045,.042,"This measures entry allocation. Complete simulation runtime was not measured.",14,GRAY)
save(fig,"opt1_stack_effect_summary")

same=[v["same_height"] for v in base["ratios_by_nkk_and_lookups"]]
changed=[v[k] for v in base["ratios_by_nkk_and_lookups"] for k in ["same_layer","large_jumps"]]
slower=[100/r for r in changed if r<1]; faster=[100/r for r in changed if r>=1]
paired=[100/v["baseline_over_candidate"] for v in pair["records"]]
assert len(paired)==18 and len(slower)==29 and len(faster)==1
calls=actual["calls"];hits=actual["hits"];misses=calls-hits
assert (calls,hits,misses)==(889446,444724,444722)
fig=plt.figure(figsize=(15,9.5),dpi=150)
label(fig,.045,.952,"#69  Reuse the index when the same height is requested again",24,weight="bold")
label(fig,.045,.906,"The particle's vertical grid stays fixed. A changed height still uses the original search.",16,GRAY)
label(fig,.045,.845,"Observed in two synthetic terrain projects",18,weight="bold")
label(fig,.045,.808,f"{calls:,} calls on the instrumented cache path; NKK = 39",16,GRAY)
ax=fig.add_axes([.075,.665,.85,.091]);ax.set_xlim(0,calls);ax.set_ylim(0,1);ax.axis("off")
ax.barh(.5,misses,height=.9,color=GRAY);ax.barh(.5,hits,left=misses,height=.9,color=BLUE)
ax.text(misses/2,.5,f"{misses:,} original searches",ha="center",va="center",fontsize=20,color="white",weight="bold")
ax.text(misses+hits/2,.5,f"{hits:,} reused indices",ha="center",va="center",fontsize=20,color="white",weight="bold")
label(fig,.075,.621,"About 50% of these lookups reused an index. This is a call count, not a runtime reduction.",15,GRAY)
label(fig,.045,.557,"Measured lookup time in separate synthetic benchmarks",18,weight="bold")
label(fig,.045,.517,"Baseline = 100%. Lower is faster. Ranges span conditions; each value is a seven-round median.",14,GRAY)
ax=fig.add_axes([.27,.265,.66,.192])
ax.set_xlim(0,137);ax.set_ylim(-.55,1.5)
ax.axvline(100,color=GRAY,lw=1.2,ls="--")
ax.hlines(1,min(paired),max(paired),color=BLUE,lw=11);ax.scatter([min(paired),max(paired)],[1,1],color=BLUE,s=50,zorder=3)
ax.hlines(0,min(slower),max(slower),color=ORANGE,lw=11);ax.scatter(faster,[0],color=ORANGE,s=75,zorder=4)
ax.text((min(paired)+max(paired))/2,1.24,f"{min(paired):.1f}% to {max(paired):.1f}%",ha="center",fontsize=16,color=BLUE,weight="bold")
ax.text((min(slower)+max(slower))/2,.25,f"{min(slower):.1f}% to {max(slower):.1f}%",ha="center",fontsize=16,color=ORANGE,weight="bold")
ax.annotate(f"1 of 30: {faster[0]:.1f}%",(faster[0],0),xytext=(65,-.32),fontsize=13,color=ORANGE,arrowprops={"arrowstyle":"-","color":ORANGE})
ax.set_yticks([1,0],["50% repeated heights\n18 conditions","Changing heights\n30 conditions"]);ax.tick_params(axis="y",length=0,pad=14,labelsize=15)
ax.set_xticks([0,25,50,75,100,125]);ax.set_xticklabels(["0%","25%","50%","75%","100%","125%"]);ax.tick_params(axis="x",labelsize=14)
for side in ["top","right","left"]:ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color("#B6C5CB")
label(fig,.27,.223,"29 of 30 changing-height cases were slower; the orange dot is the faster exception.",13.5,GRAY)
label(fig,.045,.154,"The 50% repeat sequences are synthetic, not a replay of the observed Main heights.",14,GRAY)
label(fig,.045,.112,"Benchmarks include cache preparation. Main counters measure routing and alter timing.",14,GRAY)
label(fig,.045,.068,"Benefit depends on repeated heights. Complete GRAL speedup was not measured.",16,INK,weight="bold")
save(fig,"opt1_vertical_effect_summary")
qa["derived_values"]={"calls":calls,"reused":hits,"original_searches":misses,"reuse_fraction":hits/calls,"paired_elapsed_percent_range":[min(paired),max(paired)],"changed_slower_elapsed_percent_range":[min(slower),max(slower)],"changed_faster_exception_elapsed_percent":faster[0],"ranges_are_confidence_intervals":False}
(J/"figure_review.json").write_text(json.dumps(qa,indent=2)+"\n")
print(json.dumps({"status":"rendered","files":qa["files"],"derived":qa["derived_values"]}))
