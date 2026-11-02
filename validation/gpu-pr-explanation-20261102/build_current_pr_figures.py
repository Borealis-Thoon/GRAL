from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out = Path(__file__).resolve().parent / 'current_pr_figures'
out.mkdir(exist_ok=True)
# Published PR body: process start-to-exit median [min, max], seconds, n=3.
data = [
    ('Transient, 24 situations', (41.733, 40.726, 42.339), (8.092, 7.933, 8.252)),
    ('Transient, 48 situations', (89.640, 81.662, 94.656), (13.961, 13.743, 14.214)),
    ('Steady, 24 situations', (38.804, 38.356, 40.807), (7.235, 7.168, 7.294)),
    ('Steady, 48 situations', (105.685, 77.203, 202.793), (12.645, 12.584, 13.292)),
]
fig, ax = plt.subplots(figsize=(11, 5.6))
for i, (label, cpu, gpu) in enumerate(data):
    for y, vals, color, marker in ((i-.16, cpu, '#486579', 'o'), (i+.16, gpu, '#168777', 's')):
        mid, lo, hi = vals
        ax.plot([lo, hi], [y,y], color=color, lw=3, solid_capstyle='round')
        ax.scatter(mid,y,s=38,color=color,marker=marker,zorder=3)
        ax.annotate(f'{mid:.3f}', (mid, y), xytext=(5, 5), textcoords='offset points', fontsize=8, color=color)
ax.set_yticks(range(4),[x[0] for x in data])
ax.invert_yaxis()
ax.set_xlabel('Process start to exit (s)')
ax.set_xlim(0, 220)
ax.grid(axis='x',color='#e2e8eb'); ax.set_axisbelow(True)
ax.spines[['top','right','left']].set_visible(False)
ax.tick_params(axis='y', length=0)
ax.set_title('CPU and GPU elapsed time',loc='left',weight='bold',pad=18)
ax.plot([], [], color='#486579', marker='o', label='CPU')
ax.plot([], [], color='#168777', marker='s', label='GPU')
ax.legend(frameon=False,loc='lower right',ncol=2)
fig.text(.125,.025,'Markers: median; bars: min–max, 3 repeats, 16 CPU workers. Steady 48-situation CPU times vary widely.',fontsize=9,color='#475a67')
fig.tight_layout(rect=(0,.06,1,1))
for ext in ('png','svg','pdf'):
    fig.savefig(out / f'published_process_timing.{ext}',dpi=200)
plt.close(fig)

# Conceptual flow of the published b606731 implementation.
from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrowPatch
plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'pdf.fonttype': 42})
fig, ax = plt.subplots(figsize=(13, 5.9))
ax.set_xlim(0, 13); ax.set_ylim(0, 5.9); ax.axis('off')
ink, muted, border = '#183047', '#475e70', '#668093'
ax.text(.25, 5.65, 'GRAL GPU execution', fontsize=18, weight='bold', color=ink, va='top')
for x, w, title in [(.25, 3.7, 'GRAL HOST  /  CPU'), (4.6, 3.7, 'PYTHON  /  CUDA RUNTIME'), (8.95, 3.8, 'NVIDIA GPU')]:
    ax.add_patch(Rectangle((x, .65), w, 4.3, facecolor='#f8fafb', edgecolor='#c6d4dd'))
    ax.text(x+.13, 4.76, title, fontsize=10, weight='bold', color=muted, va='top')
def node(x, y, w, h, title, detail, fill):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02,rounding_size=0.05',facecolor=fill,edgecolor=border))
    ax.text(x+.14,y+h-.16,title,fontsize=11,weight='bold',color=ink,va='top')
    ax.text(x+.14,y+h-.50,detail,fontsize=9,color=muted,va='top',linespacing=1.3)
def arrow(x1,y1,x2,y2):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle='-|>',mutation_scale=12,linewidth=1.3,color=border))
node(.48,3.35,3.24,.95,'Prepare situation','Inputs, fields and source setup','#e8f1f6')
node(.48,2.15,3.24,.95,'Coordinate execution','Fresh and residual requests','#ffffff')
node(.48,.95,3.24,.95,'Write GRAL outputs','Receive and apply results','#ffffff')
node(4.83,3.20,3.24,1.10,'Persistent server','CUDA context; static input cache','#e8f1f6')
node(4.83,2.00,3.24,.95,'Dispatch batches','Fresh and residual particle work','#ffffff')
node(4.83,.95,3.24,.82,'Return results','Synchronized response','#ffffff')
node(9.18,2.65,3.34,1.35,'GPU particle work','Trajectories and output\naccumulation','#dcefeb')
arrow(3.72,3.82,4.83,3.82); arrow(3.72,2.63,4.83,2.63)
arrow(8.07,2.70,9.18,2.70)
arrow(4.83,1.36,3.72,1.36)
ax.plot([10.85,10.85,8.07],[2.65,1.36,1.36],color=border,lw=1.3)
arrow(8.75,1.36,8.07,1.36)
fig.text(.08,.045,'Steady mode runs fresh particles only; transient mode also processes residual particles.',fontsize=10,color=muted)
fig.tight_layout(rect=(0,.08,1,1))
for ext in ('png','svg','pdf'):
    fig.savefig(out / f'published_gpu_flow.{ext}',dpi=200)
plt.close(fig)
