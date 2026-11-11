"""PR #76 figure: where the particle budget goes, before and after the patch.

Data: ../checks/switch48.json. Top: one hour in which only SG 1 emits (factors 3/0/0, as in every hour of
sparse24 and in hours 1-24 of switch48). Bottom: the 48 h switching case, hour by hour (SG 1 emits in hours 1-24, SG 2 in 25-48).
The baseline allocation is the same every hour (36/36/36, from initial_particles).
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

here = Path(__file__).parent
switch = json.loads((here.parent / 'checks' / 'switch48.json').read_text(encoding='utf-8'))

COL = {1: '#1f6aa5', 2: '#e08a1e', 3: '#7a8b99'}
IDLE = '#e3e7ea'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
fig = plt.figure(figsize=(10, 6.4), dpi=200)
gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.35], hspace=0.6)

# --- top: one hour of the sparse case ---
ax = fig.add_subplot(gs[0])
base = switch['initial_particles']            # 36/36/36 in every hour of the baseline
patched = switch['hourly_particles'][0]       # hour 1 of the patched run: 108/0/0
factors = [3, 0, 0]
for row, (label, alloc) in enumerate([('V2701', base), ('This PR', patched)]):
    left = 0
    for g, n in enumerate(alloc, start=1):
        if n == 0:
            continue
        active = factors[g - 1] > 0
        ax.barh(1 - row, n, left=left, height=0.62, color=COL[g] if active else IDLE,
                edgecolor='white' if active else '#8a969f', hatch=None if active else '///', linewidth=1)
        ax.text(left + n / 2, 1 - row, f'SG {g}: {n}' + ('' if active else ' (not emitting)'),
                ha='center', va='center', fontsize=10.5, fontweight='bold',
                color='white' if active else '#3b4650')
        left += n
ax.set_yticks([1, 0], ['V2701', 'This PR'], fontweight='bold')
ax.set_xlim(0, 108); ax.set_xticks([0, 36, 72, 108])
ax.set_xlabel('particles released per hour (budget 108)')
for s in ('top', 'right', 'left'):
    ax.spines[s].set_visible(False)
ax.tick_params(axis='y', length=0)
ax.set_title('A. One hour with factors SG 1 = 3, SG 2 = 0, SG 3 = 0', loc='left', fontweight='bold', fontsize=12)


# --- bottom: 48 h switching case, hour by hour ---
ax2 = fig.add_subplot(gs[1])
hours = range(1, switch['hours'] + 1)
emit = [1 if h <= 24 else 2 for h in hours]   # SG 1 emits in hours 1-24, SG 2 in hours 25-48
for row, label in enumerate(['V2701', 'This PR']):
    y = 1 - row
    for h in hours:
        alloc = base if row == 0 else switch['hourly_particles'][h - 1]
        bottom = 0
        for g, n in enumerate(alloc, start=1):
            if n == 0:
                continue
            active = g == emit[h - 1]
            ax2.bar(h, n / 108 * 0.8, bottom=y - 0.4 + bottom, width=0.92,
                    color=COL[g] if active else IDLE, edgecolor='none')
            bottom += n / 108 * 0.8
ax2.set_yticks([1, 0], ['V2701', 'This PR'], fontweight='bold')
ax2.set_xlim(0.4, 48.6); ax2.set_ylim(-0.55, 1.55)
ax2.set_xticks([1, 12, 24, 36, 48])
ax2.set_xlabel('hour of the 48 h run')
ax2.axvline(24.5, color='#3b4650', lw=1, ls='--')
ax2.text(12.5, 1.47, 'SG 1 emits', ha='center', fontsize=10, color=COL[1], fontweight='bold')
ax2.text(36.5, 1.47, 'SG 2 emits', ha='center', fontsize=10, color=COL[2], fontweight='bold')
for s in ('top', 'right', 'left'):
    ax2.spines[s].set_visible(False)
ax2.tick_params(axis='y', length=0)
ax2.set_title('B. Particle budget per hour when the emitting source group switches', loc='left',
              fontweight='bold', fontsize=12)
ax2.legend(handles=[Patch(color=COL[1], label='SG 1 (emitting)'), Patch(color=COL[2], label='SG 2 (emitting)'),
                    Patch(color=IDLE, label='particles on a source that is not emitting')],
           loc='upper center', bbox_to_anchor=(0.5, -0.30), ncol=3, frameon=False, fontsize=9.5)
fig.text(0.01, -0.075, 'Synthetic test cases with three co-located point sources (1 kg/h base rate each, total 3 kg/h). '
         'Bar height = share of the 108 particles per hour.', fontsize=8.5, color='#5b6670')
out = Path(sys.argv[1]) if len(sys.argv) > 1 else here / 'pr76_particle_budget.png'
fig.savefig(out, bbox_inches='tight', facecolor='white')
print(out)
