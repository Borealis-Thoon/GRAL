# GRAL GPU execution for all source types

This evidence bundle supports PR #77 and source commit [`b60673164b749896c3b942d0e89753addc1c6f7b`](https://github.com/Borealis-Thoon/GRAL/commit/b60673164b749896c3b942d0e89753addc1c6f7b). The supported GPU subset includes transient and steady execution for POINT, PORTAL, LINE and AREA sources, including mixed cases. CPU remains the default, with pre-dispatch fallback for unsupported configurations. Runtime errors remain fatal. See [scope and optimization mechanisms](docs/optimization_and_scope.md) and [runtime setup](docs/runtime_setup.md).

## Study design and evidence boundary

The study contains two separate 22-run cohorts, `transient_all_sources` and `steady_all_sources`, for 44 completed measured runs. Each fixture uses a 50 x 50 concentration grid, 360,000 new particles per situation, 16 workers and logical CPUs 16 through 31. SG1 is AREA, SG2 horizontal LINE, SG3 POINT and SG4 PORTAL. All four hourly source factors are 1.

Each cohort contains six 24-situation CPU/GPU seed pairs, two additional base-seed pairs, and three 48-situation base-seed pairs. The base-seed science pair also belongs to the 24-situation timing sample and is counted once. Thus, each mode has six distinct seed offsets and three fixed-seed timing pairs per duration. Fixed-seed repeatability is predeclared for this study.

Transient situations represent consecutive model hours with residual-particle carryover. Steady situations are separate meteorological situations with a 3600-second reference interval each. The 24/48 labels do not turn steady calculations into a continuous transient history.

The primary science window uses situations 4 through 24, with all situations retained as a sensitivity view. The timing comparison excludes the first three situations and keeps process start-to-exit, observer boundary, and summed situation intervals separate. A warm PTX cache and 10 continuous seconds of the harness idle condition precede each measured run. The earlier three-group study used a different idle gate. Its timing sample is not pooled with this study.

Three disjoint prespecified seed-pair blocks define the engineering comparison. Random stream independence and bootstrap confidence coverage remain unverified. The CPU Monte Carlo scale supplies an engineering reference, not a physical equivalence margin. Physical validation and formal scientific equivalence remain unestablished.

`phase_counts` is host bookkeeping after synchronized GPU requests. It does not measure counts for individual source types inside the kernel. Source-specific evidence combines single-source functional cases, fixed source-group mapping, positive output in every mixed-case group, launch/CUDA-event records and CPU comparisons. Steady execution requires zero residual work and excludes transient-only output state.

## Results and review records

| Record | Purpose |
|---|---|
| [Frozen protocol](qa/statistical_protocol_new_modes.md) | Design, mode semantics, quiet gate, sample units, exclusions and acceptance criteria. |
| [Transient analysis](analysis/measured/transient_all_sources/analysis_summary.json) | Numerical, timing, memory and mode-contract results for transient hours. |
| [Steady analysis](analysis/measured/steady_all_sources/analysis_summary.json) | Separate numerical, timing, memory and mode-contract results for steady situations. |
| [Functional matrix](functional_v2/functional_summary.json) | 24 configurations and the bare-CPU zero-offset control. |
| [Initial implementation receipt](qa/implementation_new_modes.json) | Historical initial source/translator snapshot and regeneration checks. It does not bind the final host source. |
| [C# review](qa/csharp_new_modes_review.json) and [Python review](qa/python_new_modes_review.json) | Reviewed code scope and verification limits. |
| [Final review](qa/final_review.json) | Reviewed claims bound to final inputs, analysis and source hashes. |

The functional matrix records 18 GPU cases and six CPU fallback cases. Five fixed-seed fallback cases match their explicit CPU counterpart's decoded members. The nonfixed-seed case checks dispatch and completion only. The zero-offset observer comparison adds a control record, giving 25 records and 49 model executions. These functional executions do not enter the measured timing or seed sample sizes.

## Measured summary

All 44 runs passed completion and integrity checks. The rows below use three fixed-seed pairs per mode and duration. Speedup is the median of paired CPU/GPU ratios, not the ratio of the backend medians. CV uses sample SD divided by the mean.

| Mode / situations | CPU process median, s | GPU process median, s | Median paired speedup [min, max] | CPU / GPU CV |
|---|---:|---:|---:|---:|
| Transient, 24 | 41.733 | 8.092 | 5.131x [5.033, 5.260] | 1.96% / 1.97% |
| Transient, 48 | 89.640 | 13.961 | 6.523x [5.745, 6.780] | 7.39% / 1.69% |
| Steady, 24 | 38.804 | 7.235 | 5.413x [5.259, 5.640] | 3.32% / 0.87% |
| Steady, 48 | 105.685 | 12.645 | 8.358x [6.135, 15.257] | 51.22% / 3.06% |

The steady 48-situation CPU process times range from 77.203 to 202.793 s, with a 51.22% CV. Its speedup range is 6.135x to 15.257x. The median describes this variable three-pair sample. The records do not identify a scheduling, thermal, frequency, tiering or GC cause.

| Mode | Aggregate same-seed NMAE, % | Largest R | V range, all source groups and aggregate |
|---|---:|---:|---:|
| Transient | 0.000872 to 0.001401 | 0.000758 | 0.999945 to 1.000062 |
| Steady | 0.000958 to 0.001195 | 0.000823 | 0.999942 to 1.000049 |

These numerical screens pass for the observed fixture. Independent review completed the diagnostics and reports `engineering_pass_observed_fixture`; its raw audit passed 38,431 checks with zero failures. The six seed settings form three prespecified disjoint blocks. RNG-stream independence, formal equivalence and physical validation remain unestablished.

The steady POINT P95 diagnostic includes an individual seed discrepancy larger than its corresponding CPU interseed contrast. Consult the independent review for the block-average and individual-seed distinction. A small aggregate NMAE does not remove this diagnostic.

## Offline analysis and source tests

Use Python with NumPy and Matplotlib. Run each cohort analysis from the bundle root into a new directory outside the bundle:

```text
python -X utf8 -B analysis/analyze_study.py --study study_manifests/transient_all_sources.json --out "<external analysis root>/transient_all_sources"
python -X utf8 -B analysis/analyze_study.py --study study_manifests/steady_all_sources.json --out "<external analysis root>/steady_all_sources"
python -X utf8 -B qa/independent_scientific_review.py --confirm-models-finished --analysis-root "<external analysis root>" --out "<new external review JSON>"
```

Replace each placeholder with a quoted absolute path outside the bundle. Use the same new analysis root for both cohorts and the independent audit; each cohort output directory and the review JSON must not exist. Confirm that model processes have finished before running the audit. These commands read saved evidence and do not launch GRAL. The public cohort manifests use portable run paths. Archived summaries bind the original manifests, so use the freshly generated portable analyses for the public manifest hashes. Raw author logs retain their original content.

For C# tests, place the pinned source in `repo/` within a working copy of the bundle:

```text
git clone https://github.com/Borealis-Thoon/GRAL.git repo
git -C repo checkout --detach b60673164b749896c3b942d0e89753addc1c6f7b
```

The [host contracts](tests/GpuDispatch/HostContracts/), [mode dispatch tests](tests/NewModeDispatch/) and [source-series reader tests](tests/SourceSeriesReader/) use the compiled model. Set `HOST_TEST_PYTHON` to a verified Python executable for the host subprocess contracts. The mode test accepts a `ModelAssembly` property. The reader project currently expects `tests/candidate_artifacts/bin/GRAL/debug/GRAL.dll`. Prepare that build layout in the working copy before running these test projects. These commands are preparation instructions for a new working copy.

New model runs require explicit adaptation of the frozen validation scripts, which retain author-specific paths and controls. Match the recorded hardware, binaries, driver, affinity, cache and idle protocol to reproduce the cohort. Label changed conditions as a new cohort. Telemetry adds `psutil` and `nvidia-smi`. Analysis and plotting use NumPy and Matplotlib. The production Python server uses the standard library.

## Figure index

Each cohort has 14 figures. The links preserve separate mode folders. In timing-plot legends, "steady timing" means the post-warm-up measurement window. The cohort name identifies model mode. Scatter maps use situations 4 through 24 and model output units. The P99 difference in the seed-level plot also uses model output units.

| Figure | Transient cohort | Steady cohort |
|---|---|---|
| Situation-time repeats | [PNG](analysis/measured/transient_all_sources/figures/situation_time_repeats.png) | [PNG](analysis/measured/steady_all_sources/figures/situation_time_repeats.png) |
| Timing variability | [PNG](analysis/measured/transient_all_sources/figures/timing_variability.png) | [PNG](analysis/measured/steady_all_sources/figures/timing_variability.png) |
| 24-situation memory traces | [PNG](analysis/measured/transient_all_sources/figures/memory_walltime_24h.png) | [PNG](analysis/measured/steady_all_sources/figures/memory_walltime_24h.png) |
| 48-situation memory traces | [PNG](analysis/measured/transient_all_sources/figures/memory_walltime_48h.png) | [PNG](analysis/measured/steady_all_sources/figures/memory_walltime_48h.png) |
| 24-situation sampled memory peaks | [PNG](analysis/measured/transient_all_sources/figures/memory_per_situation_24h.png) | [PNG](analysis/measured/steady_all_sources/figures/memory_per_situation_24h.png) |
| 48-situation sampled memory peaks | [PNG](analysis/measured/transient_all_sources/figures/memory_per_situation_48h.png) | [PNG](analysis/measured/steady_all_sources/figures/memory_per_situation_48h.png) |
| Base-seed CPU/GPU/difference maps | [PNG](analysis/measured/transient_all_sources/figures/seed0_mean_spatial_maps.png) | [PNG](analysis/measured/steady_all_sources/figures/seed0_mean_spatial_maps.png) |
| Same-seed scatter, situations 4 through 24, model output units | [PNG](analysis/measured/transient_all_sources/figures/seed_twins_scatter.png) | [PNG](analysis/measured/steady_all_sources/figures/seed_twins_scatter.png) |
| Disjoint prespecified R/V blocks | [PNG](analysis/measured/transient_all_sources/figures/seed_R_V_blocks.png) | [PNG](analysis/measured/steady_all_sources/figures/seed_R_V_blocks.png) |
| Seed-level metrics, P99 difference in model output units | [PNG](analysis/measured/transient_all_sources/figures/seed_level_metrics.png) | [PNG](analysis/measured/steady_all_sources/figures/seed_level_metrics.png) |
| 24-situation GPU pipeline | [PNG](analysis/measured/transient_all_sources/figures/gpu_pipeline_phases_24h.png) | [PNG](analysis/measured/steady_all_sources/figures/gpu_pipeline_phases_24h.png) |
| 48-situation GPU pipeline | [PNG](analysis/measured/transient_all_sources/figures/gpu_pipeline_phases_48h.png) | [PNG](analysis/measured/steady_all_sources/figures/gpu_pipeline_phases_48h.png) |
| 24-situation application buffer accounting | [PNG](analysis/measured/transient_all_sources/figures/gpu_buffer_reuse_24h.png) | [PNG](analysis/measured/steady_all_sources/figures/gpu_buffer_reuse_24h.png) |
| 48-situation application buffer accounting | [PNG](analysis/measured/transient_all_sources/figures/gpu_buffer_reuse_48h.png) | [PNG](analysis/measured/steady_all_sources/figures/gpu_buffer_reuse_48h.png) |

## Provenance and historical evidence

The bundle includes `MANIFEST_SHA256.json`, the master `study_manifest_new_modes.public.json`, and cohort manifests at `study_manifests/<cohort>.json` with portable run paths. Originals remain at `provenance/<cohort>.original.json`. Archived summaries bind the original manifests; fresh portable analyses bind the public manifests. Source and analysis hashes, execution receipts and the final review document the associated evidence. Verify the inventory and review bindings before using a working copy.

The [current translator](translator/) contains the four-field rectangular time-series transport update. The historical initial receipt in `qa/implementation_new_modes.json` records two matching regenerations. The study freeze and final review bind the final source hashes. The [previous three-group evidence](https://github.com/Borealis-Thoon/GRAL/tree/c27c54bf92c4f3d9819f7cc032fb69d98784cbc0/validation/gpu-general-20261102) and [earlier translator/tests](https://github.com/Borealis-Thoon/GRAL/tree/1961e2583e8e2a213a32c6d61a48090668ba1f80/validation/gpu-v2701-20261102) remain historical records. Their results do not replace the new four-source cohorts.
