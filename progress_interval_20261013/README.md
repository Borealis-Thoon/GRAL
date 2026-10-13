# Keep small fixed-seed particle runs complete

The fixed-seed particle driver calculates its progress interval as `(int)(NTEILMAX * 0.1F)`. With one to nine particles, that interval is zero. Each worker tracks one particle, reaches `index % percent10`, then leaves its loop through the existing exception handler. The run can finish with particles still unprocessed.

This patch changes one line to `Math.Max(1, (int)(Program.NTEILMAX * 0.1F))`. It keeps the progress divisor positive and lets the worker continue through its assigned particles. Counts of ten or more retain the original interval.

A full Main test used a 200 m square field, one area source emitting 1 kg/h, a 30-second transient situation and six allocated particles. With one worker, the original build logged 0.00139 kg emitted; the fixed build logged 0.00833 kg, matching the configured 0.008333333 kg after log rounding. With four workers, the original build logged 0.00556 kg and the fixed build again logged 0.00833 kg. Twenty-four workers could already visit all six particles before each worker stopped.

## Validation

- The actual compiled `ParallelParticleDriver` was exercised in 288 cases per build: counts 0 through 10, 11, 19, 20, 100 and 3000; one, four and 24 workers; both driver modes; three repetitions. In separate diagnostic source copies, the particle-body call is replaced by an interlocked visit counter. The fixed build visited every requested index exactly once. The original build omitted particles in 39 cases.
- Uninstrumented Main ran 90 times across five particle counts, three worker counts, two builds and three repetitions. Six further Main runs used the final source after removing an unintended UTF-8 BOM; their payloads matched the earlier candidate runs.
- One-worker output payloads at 10, 100 and 3000 particles were identical between builds in all nine paired comparisons. Parallel output retains its existing floating-point addition-order variation.
- The baseline, candidate, two diagnostic builds and final candidate all built with warnings treated as errors: zero warnings and zero errors.
- The one-line patch also passes `git apply --check` against the worker-buffer source used for #73.

## Reproduce

Use Git, Python 3 and the .NET 10 SDK on Windows. The GRAL checkout must contain base commit `891225b2f9dbbcda7f5ef6e9ef6db65e64845108`. Choose a new work directory. The helper verifies the normalized hashes of every source file before building. A process has a 60-second Main timeout; the Main suite has an 800-second cap. `DOTNET_EXE` can select another installed dotnet executable.

```powershell
python prepare.py --source-repo <GRAL-checkout> --work-dir <new-work-directory>
python <new-work-directory>/reproduce.py
```

`progress_interval.patch` is the complete engine change: one added and one removed line, totaling 147 changed characters including indentation and excluding line endings and diff signs. The progress clamp was already present in the earlier local active-source allocation work. This proposal extracts that independent correction from #55.

`results/driver_visits.csv` summarizes coverage; the two probe JSON files retain every index count. `results/main.csv` reports emitted mass and concentration summaries. `results/main.json` adds payload hashes and paired comparisons. `example_input/` contains the six-particle, one-worker case; `reproduce.py` generates every input used by the 90-run suite. The figures can use `results/figure_data.json`; values labeled as logged mass retain the engine's rounding.

[Before and after figure](figures/progress_interval.png) and [editable SVG](figures/progress_interval.svg). Run `python render_figure.py` to redraw the figure from `figure_data.json`.
