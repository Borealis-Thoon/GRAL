The source lookup patch replaces repeated linear scans with cumulative counts built once per `StartCoordinates.Calculate()` call. Four local double arrays cover point, portal, line and area sources. Binary search selects the first cumulative count greater than or equal to the particle index, including when zero source counts produce repeated prefixes. The existing source-type checks and integer offsets retain their order; random-number calls, mass calculation and source-group assignments stay unchanged.

The source-only change is in `Anfangko.cs`, with 44 lines added and 40 removed. Added and removed source-line bodies total 3842 characters, including indentation and comments but excluding line terminators. The standard Git patch has 6415 characters and bytes; the separate LF-normalized unified patch has 6198 characters. The candidate source commit is `25e96a82e4535e7ca10c2ee3273a111c23025f58`, based on the warning cleanup commit `3cfbd25505c21034673d2c850c368e953d08ef7e` for V2701. F and the residual-particle PRs cover separate topics. This suite compares S with the warning-free baseline and does not claim a combined production run.

The extra numeric payload is `8 * (M + 4)` bytes, where `M = PS_Count + TS_Count + LS_Count + AS_Count`. Array objects and references captured by the particle loop add overhead. The arrays are local to each Calculate call and are rebuilt for the current particle counts. This is an allocation cost for the lookup arrays, not a measurement of total process memory.

The final suite passed 76 Main runs with 916 checks across 19 conditions. It used a 200 m by 200 m field with 20 m grids, a fixed seed and one worker, with actual allocations of 100, 1000 or 3000 particles. Each synthetic weather situation integrates for 30 seconds. Hourly input labels index the situations and do not represent one hour of physical integration. The cases cover the four individual source types, mixed sources, a larger point-source list, receptors, deposition, odour and multiple slices. Most use wind speed 1 m/s and stability class 4; other cases prescribe stability classes 2 and 6 and changing emission factors.

All 38 baseline/candidate pairs and 38 fixed-seed repeat pairs matched their compared payloads, covering 162 payload comparisons. The suite checked 232 concentration payloads, 52,800 stored float values and four checkpoint payloads. The transient schedule also checks parsed emission totals and cumulative mass. The existing allocator keeps source particle counts between situations, so changing rates changes particle mass without reallocating those counts. This patch preserves that behaviour.

The component fixture passed 991,352 checks, including 743,036 source searches. It compared complete `StartCoordinates` results from both compiled DLLs in 24 state pairs, checking ten arrays per pair with one and two workers. These component cases use 100, 154 or 4864 particles. They are separate from the Main allocation range. Zero counts, repeated prefixes and changing count arrays are included. All three strict Release rebuilds had 0 warnings and 0 errors with `TreatWarningsAsErrors=true`.

The isolated lookup benchmark covers one source list and its prefix. It uses seven rounds with 40 batches per round, including prefix construction in each candidate batch. The production Calculate call builds four prefixes; the benchmark does not time that complete initialization. Its 1,000 and 3,000 query counts describe the lookup benchmark. They are not additional Main particle-budget cases. Median batch times are in `qa/lookup_benchmark.csv`:

| Sources | Queries | Baseline median, ms | Candidate median, ms | Baseline/candidate ratio |
|---:|---:|---:|---:|---:|
| 16 | 1000 | 0.003485 | 0.01176 | 0.296343537414966 |
| 16 | 3000 | 0.008767500000000001 | 0.0339025 | 0.2586092471056707 |
| 256 | 1000 | 0.0755425 | 0.02324 | 3.250537865748709 |
| 256 | 3000 | 0.20629 | 0.06048 | 3.4108796296296298 |
| 4096 | 1000 | 0.9291525 | 0.0216325 | 42.95169305443199 |
| 4096 | 3000 | 2.8412724999999996 | 0.0679075 | 41.84033427824614 |

The candidate is about 3.37 to 3.87 times slower with 16 sources. It is about 3.25 to 3.41 times faster with 256 sources and 41.84 to 42.95 times faster with 4,096 sources on this host. The small-list regression remains open for the author's review. The measurements exclude full initialization and geometry, dispersion, meteorology and I/O, so they do not establish an end-to-end or production speedup. The final validation suite took about 29.41 seconds; that is the suite duration, not the duration of the full review workflow.

Fixed-seed full-output equality applies to the tested one-worker Main cases. Timing changes can change `Environment.TickCount` seeds. The two-worker comparison covers only the separate start-coordinate component fixture; it does not guarantee multiworker full-model equality. Source count arrays are assumed nonnegative, as in valid model input; invalid negative counts are outside this patch. Existing Int32 offsets are preserved, and totals beyond the existing allocator's range remain outside the contract.

The public bundle includes source, synthetic inputs, reproduction code, summary CSV/JSON files and figures. Raw model output files, binary checkpoints and compiled DLLs stay in the full local validation pack and are regenerated by the runner. The production sources contain no test instrumentation.

Use a verified Python executable and .NET 10 SDK. `validate.py` requires `--run-dir` and `--dotnet`. It also accepts `--package-root` and `--template`, defaulting to the package root and its `inputs/template` directory. The .NET argument must be the actual executable path, because the runner resolves it as a path rather than searching PATH. For example, from the package root in PowerShell:

```powershell
$pythonExe = "<full path to a verified Python executable>"
$dotnetExe = (Get-Command dotnet -CommandType Application).Source
& $pythonExe -X utf8 -B reproduce/validate.py --dotnet $dotnetExe --run-dir ../patchS-check-01
```

Set `$pythonExe` to the actual interpreter path and confirm that `$dotnetExe` is the .NET 10 CLI you intend to use. Use a new isolated run directory. The runner copies sources and builds into that directory, checks source hashes, and generates the synthetic cases there. The full suite has a 15-minute limit; individual builds and the component fixture have 180-second limits, and each Main run has a 60-second limit. Results and logs are written under the run directory, with packaged source left unchanged.

The PR remains a draft while the author's line-by-line review is pending. The summary and figures describe the final verified run and retain the small-list performance tradeoff.
