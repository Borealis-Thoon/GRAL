"""Figures for the PR comment on the prognostic flow field (all numbers are measured values from this job; estimates are marked)."""
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Rectangle
from PIL import Image

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)
BLUE, ORANGE, GREEN, GREY, RED = "#2E6DA4", "#E08A2B", "#3C9D6B", "#9AA3AD", "#C0392B"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "font.family": "DejaVu Sans"})

# ---------------------------------------------------------------- 1. where the time goes
# whole run = wall; flow field and dispersion = GRAL console lines; rest = wall - both (mean of two runs, final/headline.jsonl)
cases = ["Street block, 5 m buildings\n160 x 160 x 45 cells", "Same area, tall buildings\n160 x 160 x 62 cells", "Larger area\n320 x 320 x 45 cells"]
det = dict(ff=[10.35, 28.6, 47.5], disp=[1.2, 1.4, 1.8], wall=[11.86, 30.32, 49.86])
wav = dict(ff=[1.6, 3.9, 6.65], disp=[1.2, 1.45, 1.75], wall=[3.08, 5.71, 8.93])
fig, ax = plt.subplots(figsize=(10.4, 4.3))
y = np.arange(3)
for off, d, label in ((-0.2, det, "reproducible results on, today"), (0.2, wav, "ordered sweeps, 16 threads")):
    ff, disp = np.array(d["ff"]), np.array(d["disp"])
    rest = np.array(d["wall"]) - ff - disp
    ax.barh(y + off, ff, 0.36, color=BLUE, label="prognostic flow field (CPU)" if off < 0 else None)
    ax.barh(y + off, disp, 0.36, left=ff, color=GREEN, label="particle dispersion (GPU)" if off < 0 else None)
    ax.barh(y + off, rest, 0.36, left=ff + disp, color=GREY, label="start-up and output" if off < 0 else None)
    for i in range(3):
        ax.text(d["wall"][i] + 0.6, y[i] + off, f"{d['wall'][i]:.1f} s  ({label})", va="center", fontsize=10)
ax.set_yticks(y, cases)
ax.invert_yaxis()
ax.set_xlim(0, 78)
ax.set_xlabel("wall time of one weather situation [s]")
ax.set_title("Reproducible-results runs with GPU particles: where the time goes", loc="left", fontsize=12)
ax.legend(loc="upper right", frameon=False, fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "ff_time_split.png", dpi=150)
plt.close(fig)

# ---------------------------------------------------------------- 2. speed of the flow field alone
fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.8), sharey=False)
# flow-field seconds (console line), measured: deterministic, exact order with n threads (+ diagnostic step), plain 16 threads
data = {
    "Street block, 5 m buildings": dict(det=10.5, wave={2: 6.5, 4: 3.6, 8: 2.1, 16: 1.6}, plain=1.6, gpu=3.6, mix=1.15),
    "Same area, tall buildings": dict(det=27.5, wave={2: 17.2, 4: 9.1, 8: 5.0, 16: 3.9}, plain=4.2, gpu=6.0, mix=2.05),
    "Larger area (320 x 320)": dict(det=45.0, wave={2: 28.8, 4: 15.5, 8: 8.6, 16: 6.6}, plain=6.9, gpu=9.9, mix=3.4),
}
for ax, (name, d) in zip(axes, data.items()):
    labels = ["one\nthread", "2", "4", "8", "16", "repro.\noff", "GPU\nordered", "GPU\nchecker"]
    vals = [d["det"]] + [d["wave"][n] for n in (2, 4, 8, 16)] + [d["plain"], d["gpu"], d["mix"]]
    cols = [RED] + [BLUE] * 4 + [GREY, ORANGE, GREEN]
    bars = ax.bar(range(8), vals, color=cols)
    bars[6].set_hatch("//"); bars[6].set_edgecolor("white"); bars[7].set_hatch(".."); bars[7].set_edgecolor("white")
    for i, v in enumerate(vals):
        ax.text(i, v + d["det"] * 0.015, f"{v:g}", ha="center", fontsize=9)
    ax.set_xticks(range(8), labels, fontsize=8)
    ax.set_title(name, fontsize=11)
    ax.set_ylim(0, d["det"] * 1.12)
axes[0].set_ylabel("flow field [s], 500 iterations")
fig.legend(handles=[Patch(color=RED, label="reproducible results on, today (one thread in the sweeps)"), Patch(color=BLUE, label="ordered sweeps, n threads (same bytes)"),
                    Patch(color=GREY, label="reproducible results off, 16 threads (results vary)"), Patch(facecolor=ORANGE, hatch="//", edgecolor="white", label="GPU, ordered sweeps (estimate from test kernels)"), Patch(facecolor=GREEN, hatch="..", edgecolor="white", label="GPU, pressure in the original order, momentum as a checkerboard (estimate; field differs)")],
           loc="lower center", ncol=2, frameon=False, fontsize=9)
fig.suptitle("Prognostic flow field: time by update order (Ryzen 9 9950X3D, CPUs 0-15; RTX 5080)", x=0.01, ha="left", fontsize=12)
fig.tight_layout(rect=(0, 0.16, 1, 0.94))
fig.savefig(OUT / "ff_speed.png", dpi=150)
plt.close(fig)

# ---------------------------------------------------------------- 3. animation of the update order
NI, NJ, T = 18, 12, 4          # columns along i, lines along j, threads
STRIP = NJ // T
THREAD_COL = ["#2E6DA4", "#3C9D6B", "#E08A2B", "#8E5BB5"]


def draw(ax, done, active, title, note, flags=()):
    ax.set_xlim(0, NI); ax.set_ylim(0, NJ); ax.set_aspect("equal"); ax.axis("off")
    for i in range(NI):
        for j in range(NJ):
            c = "#F2F4F6"
            if done[j, i] >= 0:
                c = matplotlib.colors.to_rgba(THREAD_COL[int(done[j, i])], 0.35)
            ax.add_patch(Rectangle((i, j), 1, 1, facecolor=c, edgecolor="white", lw=1.2))
    for (i, j, t) in active:
        ax.add_patch(Rectangle((i, j), 1, 1, facecolor=THREAD_COL[t], edgecolor="black", lw=1.4))
    for (i, j) in flags:
        ax.text(i + 0.5, j + 0.5, "?", ha="center", va="center", color=RED, fontsize=11, fontweight="bold")
    ax.set_title(title, fontsize=11, loc="left")
    ax.text(0, -0.9, note, fontsize=9, va="top")
    ax.annotate("", xy=(NI, -0.25), xytext=(NI - 4, -0.25), arrowprops=dict(arrowstyle="->", color="#555"), annotation_clip=False)
    ax.text(NI - 4.2, -0.25, "i", ha="right", va="center", fontsize=9, color="#555")


frames = []
steps = NI + T + 2
seq_done = np.full((NJ, NI), -1.0)
for s in range(steps * 2):
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.3))
    # (a) one thread: line after line. Shown at the same clock: it handles one column per step-of-three-threads -> far behind.
    seq_done[:] = -1
    k = (s * NJ) // (2 * T) * 1      # columns finished by one thread while the others work in parallel
    idx = 0
    active = []
    for i in range(NI):
        for j in range(NJ):
            if idx < k:
                seq_done[j, i] = 0
            elif idx == k:
                active.append((i, j, 0))
            idx += 1
    draw(axes[0], seq_done, active, "Reproducible results on, today: one thread",
         "Each column reads the new values of the columns\nbefore it. Always the same order, so always the same bytes.")
    # (b) plain parallel: every thread sweeps its strip from the start; reads across strip borders are old or new by timing
    done = np.full((NJ, NI), -1.0)
    rng = np.random.default_rng(7)
    pos = [min(NI, int(s * (0.42 + 0.16 * rng.random()) + rng.integers(0, 2))) for _ in range(T)]
    active, flags = [], []
    for t in range(T):
        done[t * STRIP:(t + 1) * STRIP, :pos[t]] = t
        if pos[t] < NI:
            for j in range(t * STRIP, (t + 1) * STRIP):
                active.append((pos[t], j, t))
            if t > 0:
                flags.append((pos[t], t * STRIP - 1))
    draw(axes[1], done, active, "Reproducible results off: several threads, results vary",
         "A column at a strip border reads a neighbour (?) that\nanother thread may or may not have updated yet.", flags)
    # (c) exact order: thread t works on step i only after thread t-1 has finished step i
    done = np.full((NJ, NI), -1.0)
    active = []
    for t in range(T):
        p = (s // 2) * 1 - t * 1 if s % 2 == 0 else (s // 2) - t
        p = s // 2 - t
        if p > 0:
            done[t * STRIP:(t + 1) * STRIP, :min(NI, p)] = t
        if 0 <= p < NI:
            for j in range(t * STRIP, (t + 1) * STRIP):
                active.append((p, j, t))
    draw(axes[2], done, active, "Ordered sweeps: several threads, same bytes",
         "Each thread waits until the strip below has finished the\nsame step. Every column sees what the single thread saw.")
    fig.suptitle("Update order of one sweep of the flow-field solver (schematic; colours = threads)", x=0.01, ha="left", fontsize=12)
    fig.tight_layout(rect=(0, 0.06, 1, 0.93))
    buf = io.BytesIO()
    fig.savefig(buf, dpi=80)
    plt.close(fig)
    buf.seek(0)
    frames.append(Image.open(buf).convert("P", palette=Image.ADAPTIVE, colors=64))
frames[0].save(OUT / "ff_update_order.gif", save_all=True, append_images=frames[1:], duration=[220] * (len(frames) - 1) + [2500], loop=0, optimize=True)
# a still for places that do not animate
frames[len(frames) // 2].convert("RGB").save(OUT / "ff_update_order_still.png")
print("figures:", [p.name for p in OUT.iterdir()])
