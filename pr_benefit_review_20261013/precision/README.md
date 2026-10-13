# Retaining small concentration contributions

The figure explains #64 with a worked arithmetic example and the previously published repeated-run measurements. The arithmetic starts at 16,777,216 and adds 1 a hundred times. A float accumulator loses all 100 increments; a double accumulator retains them through the final float conversion.

The measured panel uses 833.3 requested particles/s for 120 seconds, eight point sources, 20 m cells and four workers. The baseline varied in at most 15 of 7,200 cells; all five #64 runs agreed. The largest baseline relative cell difference was 0.000187%. The [original measurements](https://github.com/Borealis-Thoon/GRAL/blob/cb06f655aa78e2fdfe627cae3edf7f12481a3cfb/reviewer_response_20261013/README.md) contain the inputs and repeated outputs. This panel uses those records.

Run `python plot.py --out figures` with NumPy and Matplotlib to redraw the PNG and SVG. `figure_data.json` records the values and source link. Memory and runtime tradeoffs remain in the PR text.
