# Residual planning and concentration precision review

The #63 revision stops planning when its predicted release count equals the number of eligible residual entries. Each entry already has one particle, so further increases in the split divisor cannot reduce that count. The change adds an entry counter to the existing scan and leaves the split formula unchanged.

The exact planner and count methods were compiled in a fixture with an added scan counter. Across 225 conditions, including empty fields, capped split counts, mixed masses and 1/4/24 workers, all split counts matched the preceding PR. Seventy-five conditions used fewer scans. Cancellation before planning, zero/negative budgets and a zero reference brought the total to 229 checks per version. The illustrated 300-entry case with a target of 20 required six scans before the revision and one afterwards.

Four strict builds passed with zero warnings and errors. Sixteen uninstrumented Main runs covered steady sources, a strong source switching off, all sources switching off and a low particle budget on a 10 m grid. Every one of the 140 paired decompressed concentration payloads matched, including repeated runs.

The precision figure uses the previously published 120-run comparison and exact buffer-allocation fixture. It shows the size of the observed repeat differences and the measured allocations for two grid shapes. No new #64 engine measurements were needed for this review.

## Reproduce

Clone the public fork, which contains the reviewed #63 head, and run the Python script with a fresh output directory:

```powershell
git clone https://github.com/Borealis-Thoon/GRAL.git repo
& $python -X utf8 -B .erify.py --repo .epo --run-dir .eproduction --dotnet $dotnet
```

`$python` and `$dotnet` should name verified Python and .NET 10 executables. The script checks out `370084ba3d933e8cf444b33af93a34db41ba91fe`, applies the small revision, builds both engines and fixtures, and runs the paired comparisons. `source.json` records the reviewed head and candidate file hash. The input generator is copied from the earlier public residual suite.

The result JSON files contain scan counts, split counts and output hashes. The bundle excludes model output arrays, checkpoint files and executables. Run `make_figures.py` with Matplotlib to recreate the PNG and SVG figures from `figure_data.json`.

## Planner timing

A separate fixture timed the actual planner methods over 1,048,576 eligible entries, with 1, 4 and 24 workers. Each condition used 100 warmup calls per implementation, followed by seven alternating paired measurements of five calls each. The initial three-call warmup trial was excluded because it still showed JIT transitions.

| Workers | One scan, previous / revised (ms) | At the floor, previous / revised (ms) |
| ---: | ---: | ---: |
| 1 | 2.344 / 2.350 | 13.959 / 2.328 |
| 4 | 0.933 / 1.020 | 6.780 / 1.146 |
| 24 | 0.331 / 0.337 | 2.023 / 0.349 |

These are median planner times. The normal one-scan cases added 0.005 to 0.088 ms, with overlapping ranges; stopping at the floor reduced planner time by 82.8% to 83.3%. The timings exclude particle tracking. Individual measurements and ranges are in `results/planner_timing.json` and `results/planner_timing_summary.json`.

Rebuild the timing fixture with .NET 10 and run it with an output JSON path:

```powershell
& $dotnet build .\planner_timing\Timing.csproj -c Release --nologo /p:TreatWarningsAsErrors=true
& $dotnet .\planner_timingin\Release
et10.0\Timing.dll .\planner_timing_reproduced.json
```

The timing fixture's separate strict build also passed with zero warnings and errors.
