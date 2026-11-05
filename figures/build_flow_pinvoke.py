"""Execution-flow figure for GRAL PR #77 after the in-process (P/Invoke) runtime.

Same layout and palette as the earlier published_gpu_flow figure. Writes pr77_gpu_flow.png/.svg next to this script.
"""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

OUT = Path(__file__).resolve().parent
plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none'})
INK, MUTED, BORDER = '#183047', '#475e70', '#668093'

fig, ax = plt.subplots(figsize=(13, 6.3))
ax.set_xlim(0, 13)
ax.set_ylim(0, 6.3)
ax.axis('off')
ax.text(.25, 6.08, 'GRAL GPU execution', fontsize=18, weight='bold', color=INK, va='top')

# One GRAL process holds the host threads and the GPU runtime thread; the GPU sits outside it.
ax.add_patch(Rectangle((.12, .62), 8.33, 4.88, facecolor='none', edgecolor='#9fb3c2', linestyle=(0, (5, 3)), lw=1.1))
ax.text(.25, 5.38, 'ONE GRAL PROCESS (.NET)', fontsize=9.5, weight='bold', color=MUTED, va='top')
for x, w, title in [(.25, 3.7, 'GRAL HOST  /  CPU'), (4.6, 3.7, 'GPU RUNTIME THREAD  /  C#'), (8.95, 3.8, 'NVIDIA GPU')]:
    ax.add_patch(Rectangle((x, .75), w, 4.3, facecolor='#f8fafb', edgecolor='#c6d4dd'))
    ax.text(x + .13, 4.86, title, fontsize=10, weight='bold', color=MUTED, va='top')


def node(x, y, w, h, title, detail, fill):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.02,rounding_size=0.05', facecolor=fill, edgecolor=BORDER))
    ax.text(x + .14, y + h - .16, title, fontsize=11, weight='bold', color=INK, va='top')
    ax.text(x + .14, y + h - .50, detail, fontsize=9, color=MUTED, va='top', linespacing=1.3)


def arrow(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>', mutation_scale=12, linewidth=1.3, color=BORDER))


node(.48, 3.45, 3.24, .95, 'Prepare situation', 'Inputs, fields and source setup', '#e8f1f6')
node(.48, 2.25, 3.24, .95, 'Coordinate execution', 'Fresh and residual requests', '#ffffff')
node(.48, 1.05, 3.24, .95, 'Write GRAL outputs', 'Receive and apply results', '#ffffff')
node(4.83, 3.08, 3.24, 1.20, 'Start once per run', 'CUDA context; NVRTC compile or\nkernel cache; static input cache', '#e8f1f6')
node(4.83, 2.00, 3.24, .95, 'Dispatch batches', 'Fresh and residual particle work', '#ffffff')
node(4.83, 1.05, 3.24, .82, 'Return results', 'Synchronized response', '#ffffff')
node(9.18, 2.75, 3.34, 1.35, 'GPU particle work', 'Trajectories and output\naccumulation', '#dcefeb')
ax.text(4.73, 4.60, 'calls the CUDA driver and NVRTC directly from C#', fontsize=8.5, color=MUTED, va='top', style='italic')
arrow(3.72, 3.92, 4.83, 3.92)
arrow(3.72, 2.73, 4.83, 2.73)
arrow(8.07, 2.80, 9.18, 2.80)
arrow(4.83, 1.46, 3.72, 1.46)
ax.plot([10.85, 10.85, 8.07], [2.75, 1.46, 1.46], color=BORDER, lw=1.3)
arrow(8.75, 1.46, 8.07, 1.46)
fig.text(.08, .045, 'Requests and results travel as frames through in-process pipes. Steady mode runs fresh particles only; '
         'transient mode also processes residual particles.', fontsize=10, color=MUTED)
fig.tight_layout(rect=(0, .07, 1, 1))
for ext in ('png', 'svg'):
    fig.savefig(OUT / f'pr77_gpu_flow.{ext}', dpi=200 if ext == 'png' else None, facecolor='white')
plt.close(fig)
print('written', OUT / 'pr77_gpu_flow.png')
