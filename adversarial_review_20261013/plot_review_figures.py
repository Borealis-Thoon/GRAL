from pathlib import Path
import json,shutil,hashlib,os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path)
args=parser.parse_args()
P=Path(__file__).resolve().parent;I=P/'plot_inputs';F=args.output or P/'figures'
F.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":12,"svg.fonttype":"none"})
BLUE="#147f89";ORANGE="#b86519";INK="#263940";GREY="#637680";LIGHT="#edf3f5"
def base(title,subtitle,h=7.4):
 f=plt.figure(figsize=(15,h),facecolor="white")
 f.text(.04,.93,title,size=23,weight="bold",color=INK)
 f.text(.04,.875,subtitle,size=12.5,color=GREY)
 return f
def save(f,name):
 for ext in ("png","svg"):f.savefig(F/(name+"."+ext),dpi=160,facecolor="white")
 plt.close(f)
d=json.loads((I/"seed_contexts.json").read_text());rows=d["contexts"]
assert len(rows)==12 and len({(r["upstream_w"],r["upstream_z"]) for r in rows})==1
assert len({(r["candidate_w"],r["candidate_z"]) for r in rows})==12
f=base("#60  Separate the starting seeds of residual particles","Fixed seed; same horizontal cell and weather situation; vertical layer, source group and split index vary.")
ax=f.add_axes([.14,.34,.81,.40]);ax.set_xlim(-.75,11.75);ax.set_ylim(-.7,1.7)
colors=plt.get_cmap("tab20").colors
for i,r in enumerate(rows):
 for y,c,label in [(1,GREY,"old"),(0,colors[i],f"P{i+1}")]:
  ax.add_patch(patches.FancyBboxPatch((i-.40,y-.26),.8,.52,boxstyle="round,pad=0.02",facecolor=c,edgecolor="white"))
  ax.text(i,y,label,ha="center",va="center",color="white" if y==1 else "black",weight="bold",size=14)
ax.set_yticks([1,0],["Before\n1 pair","After\n12 pairs"]);ax.tick_params(axis="y",length=0,pad=18,labelsize=15)
ax.set_xticks(range(12),[f'k={r["k"]}\nSG={r["source_group"]}\np={r["split"]}' for r in rows]);ax.tick_params(axis="x",length=0,labelsize=11,pad=10)
for sp in ax.spines.values():sp.set_visible(False)


f.text(.08,.23,"Labels identify initial seed pairs; they are not random draw values. k = layer; SG = source group; p = split index.",size=11.5,color=GREY)
f.text(.08,.16,"The original initialization gives all 12 contexts the same pair. The patch includes their residual identities.",size=13,color=INK)
f.text(.08,.095,"Current PR head replay of 12 selected contexts (i = 15, j = 21, situation = 7).",size=11.5,color=GREY)
f.text(.08,.05,"This demonstrates the repeated-seed defect; it does not establish globally collision-free or statistically independent streams.",size=11.5,color=GREY)
save(f,"pr60_seed_identity")
d=json.loads((I/"active_reference.json").read_text())["reference_example"]
assert d["nominal_reference"]==d["continuous_all_off"]==d["restart_all_off"]
f=base("#62  Use active sources to set the residual split reference","When sources are active, include only their nominal rates. When all are off, use the nominal fallback.",7.8)
ax=f.add_axes([.07,.30,.86,.46]);ax.axis("off")
headers=["Condition","Reference value*","Result for this residual"]
cells=[["Nominal-only rule",f'{d["nominal_reference"]:.0f}',"1 trajectory"],["One source active",f'{d["active_reference"]:.0f}',"11 trajectories"],["All sources off",f'{d["continuous_all_off"]:.0f}',"1 trajectory"]]
tab=ax.table(cellText=cells,colLabels=headers,cellLoc="left",colLoc="left",bbox=[0,.05,1,.95],colWidths=[.40,.23,.37])
tab.auto_set_font_size(False);tab.set_fontsize(16)
for (r,c),cell in tab.get_celld().items():
 cell.set_edgecolor("white");cell.PAD=.07
 cell.set_facecolor(INK if r==0 else "#e3f1f0" if r==2 else LIGHT)
 cell.set_text_props(color="white" if r==0 else INK,weight="bold" if r==0 or c==2 else "normal")
f.text(.08,.245,"All-off reference: continuous run = fresh restart = nominal fallback.",size=16,color=BLUE,weight="bold")
f.text(.08,.17,"The fallback avoids retaining a reference that depends on the preceding emission situation.",size=13,color=INK)
f.text(.08,.115,"* Rounded fixture values; residual mass is approximately 100, with K = 10. Source activation uses factor > 0.",size=11.5,color=GREY)
f.text(.08,.067,"A positive factor's magnitude does not weight the nominal rate. More trajectories change sampling, not emitted mass.",size=11.5,color=GREY)
f.text(.08,.023,"Actual DLL reference-policy fixture replay. These values are not estimates of concentration accuracy.",size=11.5,color=GREY)
save(f,"pr62_active_reference")
d=json.loads((I/"adaptive_target.json").read_text())
f=base("#63  Plan residual splitting toward a soft target","Start at K = 10; increase K only if needed; stop after at most six adjustments.",7.8)
ax=f.add_axes([.04,.30,.92,.45]);ax.axis("off")
names=[("feasible_target","Target can be reached"),("entry_lower_bound","One-per-entry minimum"),("six_pass_limit","Six-adjustment limit")]
heads=["Fixture","Entries","Target","Initial count","Final count","Outcome"]
cells=[]
for key,label in names:
 x=d[key];cells.append([label,f'{x["entries"]:,}',f'{x["budget"]:,}',f'{x["initial_count"]:,}',f'{x["final_count"]:,}',"At target" if x["within_target"] else "Above target"])
tab=ax.table(cellText=cells,colLabels=heads,cellLoc="left",colLoc="left",bbox=[0,0,1,1],colWidths=[.27,.105,.105,.145,.145,.23])
tab.auto_set_font_size(False);tab.set_fontsize(14)
for (r,c),cell in tab.get_celld().items():
 cell.set_edgecolor("white");cell.PAD=.055;cell.set_facecolor(INK if r==0 else LIGHT)
 cell.set_text_props(color="white" if r==0 else BLUE if r==1 and c==5 else ORANGE if r>1 and c==5 else INK,weight="bold" if r==0 or c==4 else "normal")
f.text(.07,.225,"The target is not a hard cap: retained entries and the adjustment limit can keep the total above it.",size=14,color=INK,weight="bold")
f.text(.07,.145,"Every eligible entry keeps at least one trajectory. Larger K reduces subdivision and can increase sampling noise.",size=12,color=GREY)
f.text(.07,.09,"The prepass adds grid scans; cases already below the target keep K = 10.",size=12,color=GREY)
f.text(.07,.037,"Actual DLL planning fixtures. Predicted counts are not a measured whole-model speedup or an accuracy estimate.",size=11.5,color=GREY)
save(f,"pr63_soft_target")

d=json.loads((I/'opt1_operational_context.json').read_text())
f=base('OPT1 in existing application runs: package-level result',
       '36 weather situations; 8,000 new particles/s; four comparisons with the same machine and seed.',8.2)
ax=f.add_axes([.10,.34,.78,.40])
ys=list(range(4))
ax.barh([y+.16 for y in ys],[100]*4,height=.29,color=GREY,label='Previous engine + launcher')
ax.barh([y-.16 for y in ys],[r['optimized_time_normalized'] for r in d['timing']],height=.29,color=BLUE,label='Full OPT1 engine + launcher')
for y,r in zip(ys,d['timing']):
 ax.text(102,y,f"{r['speedup']:.2f}x",va='center',weight='bold',size=15,color=BLUE)
ax.set_yticks(ys,[f"Pair {r['pair']}" for r in d['timing']]);ax.invert_yaxis()
ax.set_xlim(0,116);ax.set_xticks([0,25,50,75,100]);ax.set_xlabel('Summed situation wall time, normalized to previous package = 100')
ax.spines[['top','right','left']].set_visible(False);ax.tick_params(axis='y',length=0,pad=12)
ax.legend(loc='lower left',bbox_to_anchor=(0,1.01),ncols=2,frameon=False)
f.text(.10,.235,'41.1% to 45.0% less time for the complete package in these comparisons.',size=16,color=INK,weight='bold')
f.text(.10,.17,'Six concentration comparisons: normalized absolute difference 0.0000579% to 0.0003065%.',size=12,color=GREY)
f.text(.10,.125,'The hourly top 1% cell sets and the period peak locations were unchanged in those six comparisons.',size=12,color=GREY)
f.text(.10,.068,'Attribution: this combines many engine changes and a launcher update. It is not the gain from #68 or #69 alone.',size=11.5,color=INK)
f.text(.10,.025,'Existing application evidence; no new production run. Underlying research fields are not included in this package.',size=11.5,color=GREY)
save(f,'opt1_operational_context')
d=json.loads((I/'precision_operational_context.json').read_text())
f=base('Higher particle counts exposed accumulation loss',
       'Historical application: six nighttime situations; 8,000 versus 30,000 particles/s.',8.3)
ax=f.add_axes([.10,.35,.83,.43]);xs=list(range(1,7))
ax.axhline(1,color=GREY,ls=':',lw=1.5,label='Equal concentration sum')
ax.plot(xs,d['stock_ratios'],'o-',color=ORANGE,lw=2.5,ms=8,label='Earlier float build')
ax.plot(xs,d['patched_ratios'],'s-',color=BLUE,lw=2.5,ms=7,label='Historical F + S + late NaN guard')
ax.set_xticks(xs);ax.set_xlim(.8,6.2);ax.set_ylim(.45,1.16);ax.set_xlabel('Nighttime situation')
ax.set_ylabel('Concentration-sum ratio: 30k / 8k')
ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15)
ax.legend(loc='upper left',frameon=False,ncols=2,fontsize=11)
ax.annotate('Minimum 0.5924',xy=(4,d['stock_min']),xytext=(3.35,.505),color=ORANGE,weight='bold',arrowprops={'arrowstyle':'-','color':ORANGE})
ax.annotate('All six: 0.9981 to 1.0019',xy=(5,d['patched_min']),xytext=(3.8,.89),color=BLUE,weight='bold',arrowprops={'arrowstyle':'-','color':BLUE})
f.text(.10,.235,'With the double-accumulation bundle, the high-cell sums stayed close as particle rate increased.',size=14,color=INK,weight='bold')
f.text(.10,.17,"Each ratio uses that configuration's own 8k top-1% positive-concentration cells, then sums both runs there.",size=11.5,color=GREY)
f.text(.10,.125,'Fresh-emission field at 2 m; 48 source groups. This comparison does not establish atmospheric accuracy.',size=11.5,color=GREY)
f.text(.10,.071,'Attribution: the historical build also enabled S and a late NaN guard. This is not a rerun of current PR #64.',size=11.5,color=INK)
f.text(.10,.026,'All six recorded ratios are shown; the two minima occur in different situations.',size=11.5,color=GREY)
save(f,'precision_operational_context')
print("figures 5 generated")