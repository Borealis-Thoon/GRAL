# GRAL NaNGuard and OPT1 review evidence

Four independent changes to the V2701 development source are included for review. Each candidate starts from the warning-free baseline used by PR #59, commit `3cfbd25505c21034673d2c850c368e953d08ef7e`.

Contents: [changes](#changes), [recorded validation](#recorded-validation), [reproduction](#reproduction), [limits](#limits).

## Changes

| Candidate | Problem and small change | Expected effect and cost |
|---|---|---|
| [`nan_guard_state`](https://github.com/GralDispersionModel/GRAL/pull/66) | A non-finite particle state can reach later indexing or accumulation. Finite checks at selected driver boundaries follow the existing removal path and count rejected states. | Stops the invalid remainder on these paths; earlier valid contributions remain. Discarded remainder is not redistributed. |
| [`nan_guard_storage`](https://github.com/GralDispersionModel/GRAL/pull/67) | A bad residual write can make a `Conz5d` cell non-finite or reach unintended indexing. Check storage inputs, the float increment and the locked prospective total. | Leaves the destination unchanged on rejection and counts rejected calls. An already polluted cell is not repaired. |
| [`opt1_stack`](https://github.com/GralDispersionModel/GRAL/pull/68) | `kko` allocates a heap array of concentration-slice indices for every fresh particle. Use stack storage for valid `NS <= 512` and retain the heap fallback above 512. | Removes the measured small-buffer entry allocation; kko stack payload is bounded at 2048 bytes. The test does not establish full-model throughput. |
| [`opt1_vertical`](https://github.com/GralDispersionModel/GRAL/pull/69) | Repeated finite adjusted heights repeat `BinarySearch()` work. Terrain particles keep one local search state and reuse the previous positive index only for an equal finite height. | Saves lookup work on repeated heights, with measurable bookkeeping overhead on changed heights. |

`source/` contains five trees with 85 source files each: `warning_free_baseline` and the four candidates above, 425 files in total. The candidates are independent; the combined tree is reconstructed by `reproduce/integrate_candidates.py`. Inputs and fixture code are included along with summary CSV/JSON files, topic diffs and figures.

Raw model outputs, checkpoint binaries, DLL/PDB files, caches, failed or superseded trials, and private paper material are excluded. The runners generate fresh local outputs and checkpoints when executed.

## Recorded validation

The recorded source validation is complete. The finished public ZIP has not yet undergone a full fresh reproduction run. Packaging checks should be read separately from the model and fixture checks below.

| Main suite | Variants tested | Executions | Passed checks | Strict build executions | Matching payload pairs |
|---|---|---:|---:|---:|---:|
| NaNGuard | Baseline, state guard, storage guard | 120 | 1896 | 3 | 760 |
| Final OPT1 | Baseline, stack, published LF vertical source | 120 | 1896 | 3 | 760 |
| Four-topic combination | Baseline, reconstructed combination | 80 | 1264 | 2 | 380 |
| Total of these suites | Baseline executions remain counted in each suite | 320 | 5056 | 8 | 1900 |

All eight strict builds passed with zero warnings and errors. The Main suites include 16 runs that actually read a checkpoint. Each independent candidate accounts for 40 executions in its own suite: 36 normal runs and four checkpoint prefix/resume runs. The 320 total is an execution count across the three suites, not 320 runs of one candidate or a factorial study. See [the final Main summary](qa/main_final_suites_summary.json).

| Separate evidence | Recorded result | Scope |
|---|---|---|
| [NaNGuard component suite](qa/nan_guard_component_summary.json) | 1917 passed checks | Shared state/storage suite: actual DLL helpers, initial driver and storage methods, plus extracted production branches. Fault injection does not cover a complete Main run. |
| [OPT1 component suite](qa/opt1_correctness.json) | 1593341 passed checks across 35 profiles | Actual DLL search and interpolation comparisons, invalidation and boundary cases. Four checks separately cover the stack declaration entry. |
| [Vertical routing profile](qa/opt1_actual_cache_hits.json) | 8 Main executions, 140 checks and 146 matching payload pairs | Four instrumented candidate runs and four baseline runs in two synthetic terrain projects. The candidate recorded 444724 hits from 889446 calls, about 50%. Counter instrumentation changes timing. |

[The profile Main summary](qa/profile_main_validation_summary.json) and [payload comparison CSV](qa/profile_main_output_comparison.csv) cover executions additional to the 320 Main executions above. The component counts are separate from the 5056 Main checks and must not be assigned in full to each individual patch.

The synthetic dispersion domain is 200 m by 200 m, with actual allocations of 100, 1000 or 3000 particles and 30 seconds per weather situation. The terrain cases also construct a 400 m by 400 m coarse grid and prescribe wind input. They exercise GRAL's terrain/wind reading path; no GRAMM solver was run. Hour labels index the short situations and do not mean physical hours of integration.

### Performance evidence

The stack entry benchmark reaches the actual `Calculate()` allocation and then exits through the initial out-of-domain removal path. Measured heap bytes per call were 32 to 0 for `NS=1`, 64 to 0 for `NS=9`, 2072 to 0 for `NS=512`, and 2080 unchanged for `NS=513`. 

The vertical lookup benchmarks include fresh state preparation and seven timing rounds. In the 45-condition sweep, all 15 same-height conditions were 1.735 to 5.408 times faster. Of 30 changed-height conditions, 29 took 4.326% to 28.135% longer and one was 1.051 times faster. A separate 18-condition synthetic sequence benchmark with exactly 50% consecutive repeats was 1.148 to 1.585 times faster in every condition, with 36 checksum comparisons matching. It is not a replay of Main height traces.

These timings measure lookup work on one host. The approximately 50% routing profile does not prove a full-model speedup or a production hit-rate distribution. [The lookup summary](qa/opt1_benchmark_summary.json) and [paired-sequence summary](qa/opt1_paired_benchmark_summary.json) retain the measured build's provenance. [The LF publication checks](qa/opt1_line_endings_validation.json) confirm fresh component success and equal compiled code across all 646 methods.

## Reproduction

The recorded Windows environment used Python 3.12.14, .NET SDK 10.0.401 and .NET runtime 10.0.12. Install these tools on the reviewer host; they are not bundled. Set the executable paths below to actual local files. Run PowerShell from the extracted bundle root.

```powershell
$Python = 'C:\path\to\python.exe'
$Dotnet = 'C:\path\to\dotnet.exe'
$PackageRoot = (Get-Location).Path
$Runs = Join-Path (Split-Path $PackageRoot -Parent) 'gral-review-runs'
& $Python --version
& $Dotnet --version
& $Dotnet --list-runtimes
```

Use a fresh run directory for each execution. The Main runner refuses an existing run directory, copies source into the new work tree and keeps build products, logs, caches, outputs and checkpoint witnesses there.

### Portable fixture and benchmark runner

`inspect` verifies the 425 shipped source files and parses the package JSON without building or running a model. The other modes require `--execute` and a fresh directory outside the extracted package. They copy the package there and build the required DLLs locally.

```powershell
& $Python -X utf8 -B .\reproduce\run_public_checks.py `
  --package-root $PackageRoot --mode inspect

& $Python -X utf8 -B .\reproduce\run_public_checks.py `
  --package-root $PackageRoot --mode nan `
  --run-dir (Join-Path $Runs 'nan-components') --dotnet $Dotnet --execute

& $Python -X utf8 -B .\reproduce\run_public_checks.py `
  --package-root $PackageRoot --mode opt1 `
  --run-dir (Join-Path $Runs 'opt1-components') --dotnet $Dotnet --execute

$TimingLock = Join-Path $Runs 'shared-timing.lock'
& $Python -X utf8 -B .\reproduce\run_public_checks.py `
  --package-root $PackageRoot --mode benchmark `
  --run-dir (Join-Path $Runs 'lookup-benchmark') --dotnet $Dotnet `
  --timing-lock $TimingLock --execute

& $Python -X utf8 -B .\reproduce\run_public_checks.py `
  --package-root $PackageRoot --mode paired `
  --run-dir (Join-Path $Runs 'paired-benchmark') --dotnet $Dotnet `
  --timing-lock $TimingLock --execute

& $Python -X utf8 -B .\reproduce\run_public_checks.py `
  --package-root $PackageRoot --mode profile `
  --run-dir (Join-Path $Runs 'routing-profile') --dotnet $Dotnet --execute
```

`nan` runs the shared guard fixture, and `opt1` runs the search/interpolation and stack-entry checks. `benchmark` runs the 45-condition lookup and stack-entry measurements; `paired` runs the 18-condition repeated-height sequences. `profile` builds the test-only counters and runs the two terrain projects with their baseline comparisons. Profile results measure routing, not speed.

For timing, keep other GRAL, GRAMM and dotnet processes out of the measurement window. The benchmark modes check for active processes, acquire a timing lock and verify source hashes before and after execution. Reuse the same `--timing-lock` path across benchmark sessions. Each mode writes a new `qa/public_reproduction_receipt.json` or failure record in its own run directory. This README's runner instructions were checked against `--help` and the code; the complete finished public bundle has not been rerun through all these modes.

### Main regression suites

The following commands use the shipped `inputs/template` and the synthetic input builder. Baseline runs are added automatically. The two commands run the individual suite groupings in the table.

```powershell
& $Python -X utf8 -B .\reproduce\validate_main.py `
  --package-root $PackageRoot --run-dir (Join-Path $Runs 'nan-main') `
  --dotnet $Dotnet --variants nan_guard_state nan_guard_storage --execute

& $Python -X utf8 -B .\reproduce\validate_main.py `
  --package-root $PackageRoot --run-dir (Join-Path $Runs 'opt1-main') `
  --dotnet $Dotnet --variants opt1_stack opt1_vertical --execute
```

Reconstruct the combined source once in a fresh extracted copy. The integrator writes `source/combined_candidate` and its scope/manifest files, and refuses to replace an existing combined tree. Then run the combined suite with its generated scope.

```powershell
& $Python -X utf8 -B .\reproduce\integrate_candidates.py `
  --package-root $PackageRoot `
  --topics nan_guard_state nan_guard_storage opt1_stack opt1_vertical --execute

& $Python -X utf8 -B .\reproduce\validate_main.py `
  --package-root $PackageRoot --run-dir (Join-Path $Runs 'combined-main') `
  --dotnet $Dotnet --variants combined_candidate `
  --scope-file .\qa\combined_scope.json --execute
```

The Main runner checks source hashes and allowed changes before and after execution, uses `TreatWarningsAsErrors=true`, and compares baseline/candidate payloads and fixed-seed repeats. Its generated `qa/main_validation_summary.json` and logs report that local run. Raw witnesses can be inspected in its run directory; none are part of this public bundle.

## Limits

Normal Main equality is established for these fixed-seed, one-worker synthetic cases. Component checks include selected two-worker tests, but full-model clock-seeded or multiworker equality is not established. Checkpoint checks compare baseline/candidate resumed payloads; they do not prove complete continuous/resumed engine-state equality.

The guards check selected finite-state and storage boundaries. They do not validate every physical input, repair a polluted checkpoint, redistribute discarded mass or undo earlier valid contributions. The vertical reuse contract requires `HOKART` to remain unchanged within a particle; arbitrary in-place grid edits while its state is live are not detected. Different finite heights always retain the original search, including heights in the same layer.

Elapsed Main times are execution-limit evidence. There is no atmospheric truth oracle, production-domain accuracy claim or whole-model speedup claim in this package. The code and review were AI-assisted; the contributor remains responsible for human line-by-line review before acceptance.
