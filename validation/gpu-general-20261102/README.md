# GRAL GPU dispatch: validation evidence

This support bundle accompanies [PR #77](https://github.com/GralDispersionModel/GRAL/pull/77) and source commit [`1a44c07ba76db21c557277a841e6904ace8b9328`](https://github.com/Borealis-Thoon/GRAL/commit/1a44c07ba76db21c557277a841e6904ace8b9328). It supports review of optional GPU dispatch for transient LINE and AREA sources and CPU fallback for unsupported configurations. The frozen protocol defines the bounded synthetic comparison.

CPU remains the default. Runtime errors remain fatal after GPU selection. See [optimization mechanisms and scope](docs/optimization_and_scope.md) and [runtime setup](docs/runtime_setup.md) for the feature boundary and environment requirements.

## Results and review records

| Record | What to inspect |
|---|---|
| [Analysis summary](analysis/measured/analysis_summary.json) | Seed comparisons, timing definitions, memory scope, numerical gates, and individual run measurements. |
| [Final review](qa/final_review.json) | Reviewed claims, decision scope, unresolved limits, and hashes linking the review to the source, study, and analysis. |
| [Frozen protocol](qa/statistical_protocol.md) and [machine-readable protocol](qa/statistical_protocol.json) | Run allocation, sampling units, exclusions, metrics, and predeclared engineering criteria. |
| [Functional matrix](functional_matrix_v2/functional_summary.json) | Case-specific dispatch and comparison status for the short functional checks. |
| [Run manifest](study_manifest.public.json) and [raw study runs](runs/study/) | Ordered run identities, relative paths, synthetic inputs, concentration outputs, logs, and telemetry. |
| [GPU phase data](analysis/measured/gpu_pipeline_phases.json) | Host phase times, CUDA-event counter differences, transfer volumes, and buffer counters. |

The study design contains 22 measured runs. Six CPU/GPU seed pairs cover 24 model hours. Two additional base-seed pairs provide three fixed-seed timing pairs at 24 hours, including the base-seed pair already in the seed analysis. Three further fixed-seed pairs cover 48 hours. Reusing the base-seed pair does not increase the number of distinct seed offsets. The primary 24-hour seed window uses hours 4 through 24, with all hours retained as a sensitivity view.

Process start-to-exit time, the sum of situation intervals after hour 3, and observer boundary time measure different intervals. The analysis keeps them separate. Device-wide GPU memory, process RSS/private bytes, and application buffer counters also have distinct meanings. Host GPU phase times include CUDA-event kernel time. Do not add the kernel time to those phase times.

The seed comparison uses CPU Monte Carlo variation as an engineering reference. Its gate does not establish physical validation or formal scientific equivalence. Three disjoint prespecified seed-pair blocks give descriptive uncertainty with limited population inference. Random stream independence is unverified. Consult the final review before using a decision label from the analysis summary.

## Figure index

| Figure | Scope |
|---|---|
| [Situation times](analysis/measured/figures/situation_time_repeats.png) | Individual fixed-seed repeats and their median, with the first three situations shaded. |
| [Timing variability](analysis/measured/figures/timing_variability.png) | Raw repeat times and medians for the separate elapsed-time definitions. |
| [24-hour memory traces](analysis/measured/figures/memory_walltime_24h.png) | Representative base-seed process memory and device-wide GPU memory versus wall time. |
| [48-hour memory traces](analysis/measured/figures/memory_walltime_48h.png) | The corresponding 48-hour memory view. |
| [24-hour memory by situation](analysis/measured/figures/memory_per_situation_24h.png) | Sampled process memory peaks across fixed-seed repeats. |
| [48-hour memory by situation](analysis/measured/figures/memory_per_situation_48h.png) | The corresponding 48-hour sampled peak view. |
| [Base-seed spatial maps](analysis/measured/figures/seed0_mean_spatial_maps.png) | CPU, GPU, and difference maps for each source group and the aggregate. |
| [Paired seed scatter](analysis/measured/figures/seed_twins_scatter.png) | Same-seed mean maps for all six offsets over hours 4 through 24, in model output units. Cells are dependent observations. |
| [Seed-pair blocks](analysis/measured/figures/seed_R_V_blocks.png) | Backend error relative to CPU variation and GPU/CPU variation ratios. |
| [Seed-level metrics](analysis/measured/figures/seed_level_metrics.png) | Raw per-seed error, bias, correlation, and P99 difference. P99 difference uses model output units. |
| [24-hour GPU phases](analysis/measured/figures/gpu_pipeline_phases_24h.png) | Host phase times, nested CUDA-event time, and transfer payloads. |
| [48-hour GPU phases](analysis/measured/figures/gpu_pipeline_phases_48h.png) | The corresponding 48-hour GPU phase view. |
| [24-hour GPU buffer reuse](analysis/measured/figures/gpu_buffer_reuse_24h.png) | Allocation/reuse/free counters and application buffer sizes. |
| [48-hour GPU buffer reuse](analysis/measured/figures/gpu_buffer_reuse_48h.png) | The corresponding 48-hour buffer view. |

## Tests, observer, and translator

The [current dispatch tests](tests/GpuDispatch/) exercise GPU eligibility, CPU fallback, and host transport contracts. The short functional matrix covers 16 configurations, including AREA, horizontal LINE, vertical LINE, a mixed supported case, one receptor, and unsupported feature combinations. The nonfixed-seed case checks dispatch and completion only. Its status must not be read as numerical parity. The matrix also records a zero-offset observer-overlay comparison with the bare CPU build. These short checks do not contribute to the measured timing or seed sample sizes.

The [observer source](validation/observer/BenchmarkTelemetry.cs) and [overlay receipt](qa/harness_overlay_v2.json) show how the external observer captures timing and seed evidence. The bundle retains test and review records separately from model results. Historical preflight or failed-development records document preparation. Keep them outside the measured replicate counts.

Earlier [GPU host tests](https://github.com/Borealis-Thoon/GRAL/tree/1961e2583e8e2a213a32c6d61a48090668ba1f80/validation/gpu-v2701-20261102/overlay/gpu/tests), [active-source allocation cases](https://github.com/Borealis-Thoon/GRAL/tree/1961e2583e8e2a213a32c6d61a48090668ba1f80/validation/gpu-v2701-20261102/overlay/tests/ActiveSources), and the [C#-to-CUDA translator](https://github.com/Borealis-Thoon/GRAL/tree/1961e2583e8e2a213a32c6d61a48090668ba1f80/validation/gpu-v2701-20261102/overlay/gpu/translator) remain pinned at the previous evidence commit. They document the underlying implementation and generation tools. Their earlier AREA-only single-run measurements are separate from this repeated mixed-source study.

## Recompute the analysis without running GRAL

Use Python with NumPy and Matplotlib. From the bundle root, run the following command with a new output directory outside the bundle:

```text
python -X utf8 -B analysis/analyze_study.py --study study_manifest.public.json --out <new directory outside bundle>
```

Replace the angle-bracket placeholder with a quoted absolute path. The output directory must not exist. This command reads the packaged runs and produces a new analysis summary and figures. It does not launch the GRAL engine. The public manifest resolves run paths relative to the bundle, so offline analysis does not require the author's original drive layout. Input, completion, dispatch, and cohort checks can reject an incomplete or altered bundle.

## Source checkout and benchmark reproduction

To run the C# tests, use a working copy of the bundle and place the pinned source checkout in its `repo/` directory. The test projects use relative references to `repo/src/GRAL.csproj`.

```text
git clone https://github.com/Borealis-Thoon/GRAL.git repo
git -C repo checkout --detach 1a44c07ba76db21c557277a841e6904ace8b9328
dotnet run --project tests/GpuDispatch/GpuDispatch.csproj -c Release
dotnet run --project tests/GpuDispatch/HostContracts/HostContracts.csproj -c Release
```

New model runs require the [runtime setup](docs/runtime_setup.md), the recorded inputs and observer overlay, and a declared execution environment. The original benchmark uses 16 workers on logical CPUs 16 through 31 for both backends. Match the recorded hardware, driver, affinity, cache condition, and binaries to reproduce that cohort. On different hardware or with changed settings, create and label a new cohort.

The frozen validation scripts retain the author's machine-specific paths and execution controls. They require review and explicit adaptation before new model runs on another machine. Validation telemetry adds `psutil` and `nvidia-smi`. Analysis and plotting add NumPy and Matplotlib. The production Python GPU server uses the standard library.

## Hashes and provenance

[MANIFEST_SHA256.json](MANIFEST_SHA256.json) inventories the packaged files. [Bundle provenance](provenance/bundle_provenance.json) records the source commit, original and public manifest hashes, and path rewrites. The [original study manifest](provenance/study_manifest.original.json) preserves the author's run locations. The public manifest changes run paths for offline use while the raw logs retain their original content.

The [analysis artifact hashes](analysis/measured/artifact_sha256.json), [frozen study record](qa/harness_study_freeze.json), and [final review](qa/final_review.json) connect inputs, source, execution, analysis, and reviewed claims. Verify these records before modifying a working copy. Recomputed output hashes can differ when the public manifest replaces the original manifest hash. Compare the recorded scientific and timing values within their declared definitions.
