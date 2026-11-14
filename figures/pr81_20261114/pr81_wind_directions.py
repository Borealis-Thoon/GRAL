"""Figure for the #81 description, bullet "Eight wind directions on the street-block case".

Change of the summed continuity residual, prognostic-only build against upstream, for
the eight wind directions: after the prognostic solver and the final sum. Reads the
analysis output of the gap-fix job, writes the PNG and a JSON with the plotted numbers
next to this script.
Run with a Python with Matplotlib (Matplotlib).
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

JOB = Path(r'<job folder>')
SOURCE = JOB / 'gapfix/cpu/t4/t4_results.json'
OUT = Path(__file__).resolve().parent
NAME = 'pr81_wind_directions'
COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
# Test A table of gapfix/cpu/t4/t4_results.md, one decimal: (after the prognostic solver, final sum)
TABLE = {'W': (-11.7, -3.3), 'E': (-19.1, -5.9), 'N': (-18.1, -2.7), 'S': (-14.9, -0.9),
         'SW': (-13.5, -2.2), 'NW': (-14.8, -2.8), 'NE': (-15.7, -3.9), 'SE': (-15.8, -2.9)}
# ranges as printed in the live #81 description
TEXT_RANGE = {'after_prognostic_solver': (-19.1, -11.7), 'final_sum': (-5.9, -0.9)}

INK, MUTED, GRID = '#1f2d3d', '#5b6b7b', '#d9e1e8'
BLUE, ORANGE = '#2f6f9f', '#d9822b'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': MUTED,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.unicode_minus': False})


def main():
    dirs = json.loads(SOURCE.read_text(encoding='utf8'))['directions']
    assert set(dirs) == set(COMPASS), sorted(dirs)
    prog = {d: dirs[d]['pexit_pct'] for d in COMPASS}
    final = {d: dirs[d]['dexit_sum_pct'] for d in COMPASS}
    for d in COMPASS:
        assert (round(prog[d], 1), round(final[d], 1)) == TABLE[d], (d, prog[d], final[d])
    got = {'after_prognostic_solver': (round(min(prog.values()), 1), round(max(prog.values()), 1)),
           'final_sum': (round(min(final.values()), 1), round(max(final.values()), 1))}
    assert got == TEXT_RANGE, got
    beyond5 = [d for d in COMPASS if round(final[d], 1) < -5.0]
    assert beyond5 == ['E'], beyond5  # "only the east wind is beyond 5 %"

    fig, ax = plt.subplots(figsize=(8.8, 4.2))
    x = np.arange(len(COMPASS))
    w = 0.38
    b1 = ax.bar(x - w / 2, [prog[d] for d in COMPASS], w, color=BLUE, label='residual after the prognostic solver')
    b2 = ax.bar(x + w / 2, [final[d] for d in COMPASS], w, color=ORANGE, label='final residual sum')
    for bars in (b1, b2):
        for r in bars:
            v = r.get_height()
            ax.text(r.get_x() + r.get_width() / 2, v - 0.35, f'{v:.1f}', ha='center', va='top', fontsize=9.5, color=INK,
                    bbox=dict(facecolor='white', edgecolor='none', pad=0.6), zorder=4)
    ax.axhline(0, color=MUTED, lw=0.9)
    ax.axhline(-5, color=MUTED, lw=1.0, ls=(0, (4, 3)), zorder=0.9)  # behind the bars
    ax.text(len(COMPASS) - 0.13, -4.75, '-5 %', va='bottom', ha='right', fontsize=9.5, color=MUTED)
    ax.set_xticks(x, COMPASS)
    ax.tick_params(axis='x', length=0, pad=6)
    ax.set_xlim(-0.6, len(COMPASS) - 0.1)
    ax.set_ylim(-22.5, 0.8)
    ax.set_yticks([0, -5, -10, -15, -20])
    ax.set_xlabel('wind from')
    ax.set_ylabel('change against upstream [%]')
    ax.grid(axis='y', color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=10, frameon=False,
              handlelength=1.4, columnspacing=2.2)
    fig.suptitle('Street-block case, eight wind directions: change of the summed continuity residual',
                 x=0.012, y=0.985, ha='left', color=INK, fontsize=12)
    fig.text(0.012, 0.905, 'prognostic-only build against upstream, reproducible mode, 8 threads',
             ha='left', color=MUTED, fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT / f'{NAME}.png', dpi=200, facecolor='white')
    plt.close(fig)

    record = {
        'figure': f'{NAME}.png',
        'quantity': 'change of the summed continuity residual in percent, build with the plus at the prognostic '
                    'line (e8e110a + instrumentation) against upstream (9d819a7 + instrumentation); '
                    'fields "pexit_pct" and "dexit_sum_pct" of "directions" in the source file',
        'source': str(SOURCE).replace('\\', '/'),
        'table_with_the_same_numbers': str(SOURCE.with_suffix('.md')).replace('\\', '/') + ' (Test A)',
        'directions_left_to_right': COMPASS,
        'plotted': {d: {'wind_from_deg': dirs[d]['deg'],
                        'after_prognostic_solver_pct': prog[d], 'after_prognostic_solver_label': f'{prog[d]:.1f}',
                        'final_sum_pct': final[d], 'final_sum_label': f'{final[d]:.1f}'} for d in COMPASS},
        'reference_line_pct': -5,
        'range_check_against_the_description': {
            k: {'text': list(TEXT_RANGE[k]), 'plotted_min_max': list(got[k]), 'agree': True} for k in TEXT_RANGE},
        'final_sum_beyond_5_pct': beyond5,
    }
    (OUT / f'{NAME}.json').write_text(json.dumps(record, indent=1), encoding='utf8')
    print('wrote', NAME, {d: (f'{prog[d]:.1f}', f'{final[d]:.1f}') for d in COMPASS})


if __name__ == '__main__':
    main()
