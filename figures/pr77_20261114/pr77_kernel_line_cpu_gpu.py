"""Figure for the #77 description, "Limitations", bullet about the second push of 14 Nov 2026.

CPU-GPU concentration difference of the seven transient test projects on the merged
tree, GPU kernel with the old and with the new line. Reads the two comparison files of
the gap-fix job, writes the PNG and a JSON with the plotted numbers next to this script.
Run with a Python with Matplotlib (Matplotlib).
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

JOB = Path(r'<job folder>')
EVID = JOB / 'gapfix/pr77/evidence'
SOURCES = {
    'old_line': EVID / 'T1_before_merged_cpu__merged_gpu.json',
    'new_line': EVID / 'T1_after_merged_cpu__wk_gpu.json',
}
OUT = Path(__file__).resolve().parent
NAME = 'pr77_kernel_line_cpu_gpu'
# ranges as printed in the live #77 description (Limitations, second-push bullet)
TEXT_RANGE = {'old_line': ('3.9e-4', '3.1e-2'), 'new_line': ('2.2e-6', '5.2e-3')}

INK, MUTED, GRID = '#1f2d3d', '#5b6b7b', '#d9e1e8'
BLUE, ORANGE, GREY = '#2f6f9f', '#d9822b', '#9aa5b1'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': INK,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.unicode_minus': False})


def sci(v):
    """2 significant figures in the form of the description, e.g. 3.9e-4."""
    mant, exp = f'{v:.1e}'.split('e')
    return f'{mant}e{int(exp)}'


def load(path):
    doc = json.loads(path.read_text(encoding='utf8'))
    # concentration files (.con) only; deposition and odour outputs are other quantities
    return {case: c['kinds']['con']['nmae'] for case, c in doc['cases'].items()}, doc


def main():
    vals, docs = {}, {}
    for key, path in SOURCES.items():
        vals[key], docs[key] = load(path)
    projects = list(vals['old_line'])
    assert set(projects) == set(vals['new_line']) and len(projects) == 7, projects
    for key, (lo, hi) in TEXT_RANGE.items():
        got = (sci(min(vals[key].values())), sci(max(vals[key].values())))
        assert got == (lo, hi), (key, got, (lo, hi))

    order = sorted(projects, key=lambda p: vals['old_line'][p])  # largest on top
    fig, ax = plt.subplots(figsize=(8.8, 4.0))
    for y, p in enumerate(order):
        old, new = vals['old_line'][p], vals['new_line'][p]
        ax.plot([new, old], [y, y], color=GREY, lw=1.6, zorder=1, solid_capstyle='round')
        ax.scatter([old], [y], s=70, marker='o', color=ORANGE, zorder=3,
                   label='old kernel line' if y == 0 else None)
        ax.scatter([new], [y], s=62, marker='s', color=BLUE, zorder=3,
                   label='new kernel line' if y == 0 else None)
        ax.text(old * 1.45, y, sci(old), va='center', ha='left', fontsize=10, color=INK)
        ax.text(new / 1.45, y, sci(new), va='center', ha='right', fontsize=10, color=INK)
    ax.set_xscale('log')
    ax.set_xlim(2e-7, 4e-1)
    ax.set_ylim(-0.6, len(order) - 0.4)
    ax.set_yticks(range(len(order)), order)
    ax.set_xlabel('sum of absolute concentration differences / sum of the CPU values (logarithmic axis)')
    ax.grid(axis='x', color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.13), ncol=2, fontsize=10, frameon=False,
              handletextpad=0.3, columnspacing=2.2)
    fig.suptitle('CPU-GPU concentration difference of the seven transient test projects, merged tree',
                 x=0.012, y=0.985, ha='left', color=INK, fontsize=12)
    fig.text(0.012, 0.905, 'RX 9070 XT, Windows, reproducible results on', ha='left', color=MUTED, fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    fig.savefig(OUT / f'{NAME}.png', dpi=200, facecolor='white')
    plt.close(fig)

    record = {
        'figure': f'{NAME}.png',
        'quantity': 'sum of absolute concentration differences over the sum of the CPU values '
                    '(field "nmae" of kind "con" in the source files), CPU run against GPU run',
        'sources': {k: str(p).replace('\\', '/') for k, p in SOURCES.items()},
        'compared_runs': {k: {'A': docs[k]['A'], 'B': docs[k]['B']} for k in SOURCES},
        'table_with_the_same_numbers': str(EVID / 'T1_table.md').replace('\\', '/'),
        'projects_top_to_bottom': list(reversed(order)),
        'plotted': {p: {'old_line': vals['old_line'][p], 'old_line_label': sci(vals['old_line'][p]),
                        'new_line': vals['new_line'][p], 'new_line_label': sci(vals['new_line'][p])}
                    for p in reversed(order)},
        'range_check_against_the_description': {
            k: {'text': list(TEXT_RANGE[k]),
                'plotted_min_max': [sci(min(vals[k].values())), sci(max(vals[k].values()))],
                'agree': True} for k in SOURCES},
    }
    (OUT / f'{NAME}.json').write_text(json.dumps(record, indent=1), encoding='utf8')
    print('wrote', NAME, [record['plotted'][p]['old_line_label'] + ' -> ' + record['plotted'][p]['new_line_label']
                         for p in record['plotted']])


if __name__ == '__main__':
    main()
