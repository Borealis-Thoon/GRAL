# Evidence for GRAL PR #77 (optional NVIDIA GPU path)

This branch holds the figures and summary data behind the PR description. It contains no source code; the code is on the PR branch. Local paths in the copied reports are replaced by `<jobs>`, `<work>` and `<user>`.

All runs used Windows 11 x64, an AMD Ryzen 9 9950X3D, one NVIDIA GeForce RTX 5080 (16 GB, CUDA 13.4 driver), NVRTC 12.9 and .NET 10. Inputs are synthetic: 2 km GRAL domains in the main study, in the supplement's `combined_ns2` and in the B00 runs of `final_build/` and `pinvoke/`; 1 km domains in the feature suite, in `true_flat` and in the inputzr.dat and vertical-file checks of `final_build/`.

## Measures

- **A**: mean absolute CPU-GPU difference for the same fixed seed.
- **B**: mean absolute difference between two CPU runs with different seeds.
- **Block**: one output layer and source group compared over one pair of seeds; it passes when A/B < 1, so the GPU stays inside the CPU's own run-to-run variability.

## Contents

| Folder | What it holds |
|---|---|
| `figures/` | The PR figures (PNG and SVG) with the scripts that draw them: parity, speed and native seeds (`build_pr_figures.py`, values in `figure_numbers.json`), the execution flow (`build_flow_pinvoke.py`) and the single-precision trial (`build_pinvoke_figures.py`, values in `precision_numbers.json`) |
| `main_study/` | 448-run study: configuration settings (`configurations.json`), 240 fixed-seed blocks, 480 repeat pairs with the same seed (`repeatability.csv`, all differences 0 in the decoded layer values), native-seed scalars, per-run timing and CPU/GPU speedups |
| `supplement/` | 56-run supplement, two configurations (`true_flat`; `combined_ns2` with two layers, four source groups, three receptors and 4 h on/off emissions): 87 fixed-seed blocks and timing |
| `feature_suite/full_50/` | 50 feature, stress and invalid-input cases, run before the seed and vertical-precision changes |
| `feature_suite/vertical_double/` | Vertical-concentration cases after the double-precision change |
| `feature_suite/vertical_precision/` | Lowest vertical layer before (float sum) and after (double sum) for the 20 highest cells of two cases, same inputs and seed |
| `feature_suite/final_code/` | 18 cases (17 with fixed seeds) re-run on eceb2eb, before the in-process runtime, without any override switch; the three commits up to 06eb66b changed end-of-run, inputzr.dat, checkpoint and log-file handling and `gpu/README.md`, not `gpu/runtime` |
| `native_seeds/` | Native-seed runs: CPU, CPU repeat, a CPU build with the old GPU seeding, the old GPU seeding (`gpu_native_old`), an intermediate TickCount-based GPU seeding (`gpu_native_new` in `native_recheck_report.json`), and CPU and GPU with hashed seeds |
| `final_build/` | Checks of 06eb66b, the PR head before the in-process runtime: build log (English, with the commit and command line; `TreatWarningsAsErrors`, 0 warnings); B00 smoke on CPU and GPU against the main-study output, inputzr.dat end-of-run cases, and a vertical-file failure followed by a rerun, all run with that build (DLL SHA256 in each file); the NVRTC compile matrix of the `generated.cu` of 06eb66b |
| `pinvoke/` | The in-process runtime (commit 25b06a0), the exact `cs_cast` change (8d40150), the launch-size default (6057195) and the single-precision trial; see the last section |

## Timing

Each timing run started after a 10 s quiet gate, but other jobs could still start during a run. A pair counts as slowed when its CPU or GPU run took more than 1.5x the fastest run of that backend among the configuration's 14 runs; 22 of the 48 pairs were slowed. The PR headline uses the other 26 pairs. Feature-suite times were not taken under this protocol, and their CPU runs used logical CPUs 0-15 (the main study used 16-31).

## Reading the feature-suite reports

`summary.md` lists each case with its harness verdict (`screen`); its wall-time column lists CPU fixed / GPU fixed / CPU native-seed runs, and GPU native-seed times are in `report.json`. The verdict also checks harness expectations that are not about CPU/GPU agreement. The per-output parity verdicts (`type_status` in `report.json`) pass for every fixed-seed case.

- `fail` in `final_code/` comes from an expectation written for an earlier build, in which these features were still routed to the CPU. `review` in `full_50/` comes from the expectations listed next to it.
- "feature effect not visible" means the fixture changed the output less than the CPU seed noise. It says nothing about CPU/GPU agreement.
- In `full_50/` the vertical cases ran with a situation range, so GRAL wrote no `Vertical_Concentrations.txt` and "feature effect not visible" there means the file was missing. Vertical parity comes from `vertical_double/` and `final_code/`.
- "gpu_metrics lines 13 != situations 12" in `vertical_double/` comes from the harness expecting 12 situations; the vertical fixture has 13.
- "stationary run wrote Receptor_Timeseries_Transient.txt" is GRAL's existing behaviour on both backends.
- "vertical: N values differ by >1 unit in the 3rd significant digit" counts cells whose CPU/GPU difference exceeds one unit of the third significant digit in the text file. Most are 2-unit differences; a few low-concentration cells differ more. The vertical A/B over the whole field is 1.1e-4 to 1.3e-4.
- `neg_*` cases are invalid or unsupported inputs. They stop the run or fall back to the CPU with a logged reason; `neg_eki_ob0` now completes, because an Obukhov length of 0 is replaced by 1.
- `neg_vertical_inf` shows `harness_error` in `full_50/` because its 1-situation probe ran with a situation range and wrote no vertical file, so the case never ran. In `vertical_double/` it shows `negative_unexpected` because the harness expected 12 GRZ files and the fixture writes 13; the GPU run fell back to the CPU with the logged reason "non-finite accumulated output", as intended.
- `steady_rot_nonfixed` uses native seeds, so an A/B near 1 is expected (1.08 in `final_code/`). In `full_50/`, which ran with the intermediate GPU seeding, it is 4.3; the hashed seeds removed that excess.

## In-process runtime, launch size and single-precision trial (`pinvoke/`, added for commits 25b06a0, 8d40150 and 6057195)

The GPU runtime moved from a Python process into GRAL: a C# thread owns the CUDA context and calls the CUDA driver and NVRTC directly. The kernel gained one exact change (`cs_cast<int>` for float arguments), and the default launch size rose from 4,096 to 65,536 particles. Unless noted, runs used B00 (24 h, synthetic 2 km domain at the origin) and logical CPUs 0-15; local paths are replaced by `<jobs>`, `<work>` and `<user>`, as elsewhere in this branch.

| Path | What it holds |
|---|---|
| `pinvoke/final_build/` | Build log of 6057195 (`TreatWarningsAsErrors`, 0 warnings); B00 smoke on CPU and GPU against the main-study output; startup failures with and without `INU_GPU_FALLBACK_ON_STARTUP=1` (B00 situations 1-2); GUI stop requests during the dispersion (`gui_stop.json`) and during GPU startup before the NVRTC compile had finished (`gui_stop_during_compile.json`), both started without the CPU 0-15 restriction; the NVRTC compile matrix of the final `generated.cu` |
| `pinvoke/host/b00_runs.json` | B00 runs of intermediate and final builds: in-process runtime with an empty and a filled kernel cache, the Python server on the same build (three runs), block size 256, the kernel with the `cs_cast` change on both runtimes, the final launch-size default against 4,096 and against no launch sizing, and the final code with the kernel cache turned off (`INU_GPU_CACHE_DIR=off`). Each row has the wall time, kernel time, launch count, compile time, cache status and the number of GRZ members identical to the main-study output |
| `pinvoke/host/cache_failures.json` | A cache folder that cannot be created and a truncated cache entry, both on the intermediate `build7`: both runs compile the kernel and finish with all 96 GRZ members identical to the main-study GPU output |
| `pinvoke/host/register_cap_sweep.json` | B00 kernel time, registers and local memory per thread with register caps of 168, 128, 96 and 64 (and none), at 4,096 particles per launch |
| `pinvoke/feature_suite/` | The 20-case feature suite on the final code (`summary.md`, `report.json`) and a byte comparison of its GPU outputs with the earlier run on `build7`, which used 4,096 particles per launch (`gpu_output_identity.json`) |
| `pinvoke/precision/` | Single-precision trial: kernel times and output differences (`runs.jsonl`, `compare.json`), the edit counts of each variant (`variants.json`), static counts of PTX instructions with an `.f64` type in the two large device functions (`Zeitschleife_Calculate`, called by `gral_fresh`, and `gral_residual`) with registers and local memory per kernel (`ptx_counts.jsonl`), and the scripts used (`tools/`) |
| `figures/pr77_gpu_flow.*`, `figures/pr77_precision.*` | The two new PR figures and their scripts; `precision_numbers.json` holds the plotted values |

### Reading the P/Invoke files

- `b00_runs.json` names the build of each run. `build6` and `build7` are intermediate local builds in which `INU_GPU_HOST=python` still selected the Python server; the final code no longer has that switch. `build9` has the source tree of 8d40150, `build10` that of 6057195, and `build_final` is the clean build of 6057195. Runs before `build10` used 4,096 particles per launch.
- Kernel time is the sum of the CUDA event times of all launches. With a filled cache, the time outside the kernels (GRAL's startup, situation setup and output, and the transfers) was 9.6 to 10.7 s per B00 run in the earlier runs (`build6`, `build9`) and 4.1 to 4.2 s in the later ones (`build10`, `build_final`). `build9` and `build10` differ only in the default launch size, and at 4,096 particles per launch they took 9.9 s and 4.2 s outside the kernels (`b9_smoke`, `q10_chunk4096`), so the difference does not come from the code; the files do not record its cause. Compare times within one period; a run that compiles the kernel adds the NVRTC compile, which took 2.3 to 5.7 s in these runs (`nvrtc_compile_ms`).
- In `gpu_output_identity.json`, a case counts as identical when the GPU run in its fixed-seed slot (`gpu_fixed`, which uses native seeds in `steady_rot_nonfixed`) writes the same output files to `Computation` as the earlier run and each of them matches byte for byte (GRZ files member by member; inputs, `*.log`, `Logfile_*` and `Problemreport*` are not compared; each `different` list names at most 10 files, and all 12 GRZ files of `steady_rot_nonfixed` differ). Eleven of the 20 cases are identical. The other nine differ for three reasons. `steady_rot_nonfixed` uses native seeds, so it draws new seeds on every run. In seven cases the GPU builds double sums with atomic additions whose order changes with the launch size and between runs, so the last digits change: `ReceptorConcentrations.dat` in five receptor cases (at most 1.2e-14 relative), and in the two wet-deposition cases with droplet drift 123 and 143 GRZ cells (of 66,398 and 86,797), each by one float rounding step (at most 1.2e-7 relative). Two earlier runs with the same kernel at 4,096 particles per launch (the `build7` run and a build of 8d40150, not published) differed in 0 and 2 cells of these two cases. The GPU run of `neg_vertical_inf` falls back to the CPU before any kernel runs; in the earlier run its `Vertical_Concentrations.txt` differed from the CPU run in 12 of 127,606 values, while the final run matches its CPU run byte for byte, so the difference comes from the CPU path with the `+Inf` restart file.
- The verdicts in `pinvoke/feature_suite/summary.md` match those of the earlier run: `vertical_conc` shows `fail` for the 13-situation count and the 26 vertical values explained in "Reading the feature-suite reports", `neg_vertical_inf` shows `negative_unexpected` as in `vertical_double/`, and the four `review` rows come from "stationary run wrote Receptor_Timeseries_Transient.txt" or "feature effect not visible" (listed under `problems` in `report.json`).

### Single-precision trial

- Variants: `D2` has the code of the final kernel. `M2` (mixed) turns trajectory scalars, casts and literals into float but keeps absolute particle and tunnel positions in double. `F2` (float) also turns the positions into float. `M` and `F` lack the float `cs_cast` overload and give the same output as `M2` and `F2`. `X2` is `M2` with the grid-relative coordinates (`xsi`, `eta`, `xsi1`, `eta1`, positions relative to the GRAL and GRAMM origins) also kept in double. State fields, output accumulators, the step-limit line and the random-number conversions stay unchanged in all variants. All variant runs used 4,096 particles per launch.
- `B00` lies between 0 and 2 km. `B00s` is the same case moved by +150 km in x and +430 km in y (`tools/shift_case.py` moves the GRAL and GRAMM extents, the GRAMM origin stored in `ggeom.asc` and every source coordinate). The CPU outputs of the two cases differ by 7.8e-8 relative (`compare.json`, key `shift: B00s cpu vs B00 cpu`).
- `relative` in `compare.json` is the sum of absolute cell differences over all GRZ members divided by the sum of the reference values. The seed-noise references are pairs of main-study CPU runs of `B00` with three different fixed seeds (0.153 to 0.155 at the origin; computed with `compare_grz.py`, the three values are listed in `figures/build_pinvoke_figures.py`) and a native-seed CPU run of `B00s` against its fixed-seed CPU run (0.182, in `compare.json`).
- The scripts in `tools/` keep the paths they ran with (local roots replaced by the placeholders above), so they document what was run and do not run as published. `compare_grz.py`, `make_variant.py` (reads `gpu/runtime/generated.cu` from a checkout of the PR) and `shift_case.py` (copies the main-study `B00` inputs) need no other code; `compare2.py` calls `compare_grz.py` on local run outputs; `runs2.py` drives a local smoke harness that is not published; `compile_check.py` imports `cuda_common.py` of the removed Python host, which is in the PR history at 06eb66b.
