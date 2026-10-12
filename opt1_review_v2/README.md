# OPT1 effect summaries

The figures summarize the existing measurements for PRs [#68](https://github.com/GralDispersionModel/GRAL/pull/68) and [#69](https://github.com/GralDispersionModel/GRAL/pull/69). The engine source and test results are unchanged.

- [Stack allocation](figures/opt1_stack_effect_summary.png): heap bytes at the production driver entry, with the stack limit and heap fallback.
- [Vertical lookup](figures/opt1_vertical_effect_summary.png): observed search reuse in two synthetic terrain projects, followed by lookup timings from separate synthetic sequences.

The timing plot uses baseline time = 100%. Each range spans the condition medians from seven rounds; it is not a confidence interval. Repeated-height timings and the observed Main call counts come from different experiments. Full simulation speedup was not measured.

The original [review package](https://github.com/Borealis-Thoon/GRAL/blob/442b383534f477dd78ca5e6ba5114329632a82e4/review_evidence/README.md) contains the full benchmarks, source, and model test procedure.

To redraw the PNG and SVG files with Python and Matplotlib, run:

```text
python plot_opt1_review.py
```

The script reads the included measurement JSON files. Redrawing these figures does not run GRAL.
