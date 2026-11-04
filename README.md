# Evidence for GRAL PR #77 (optional NVIDIA GPU path)

This branch holds the figures and summary data behind the PR description. It contains no source code; the code is on the PR branch. Local paths in the copied reports are replaced by `<jobs>`, `<work>` and `<user>`.

All runs used Windows 11 x64, an AMD Ryzen 9 9950X3D, one NVIDIA GeForce RTX 5080 (16 GB, CUDA 13.4 driver), NVRTC 12.9 and .NET 10. Inputs are synthetic: 2 km GRAL domains in the main study and in the supplement's `combined_ns2`, 1 km domains in the feature suite, in `true_flat` and in the final-commit checks.

## Measures

- **A**: mean absolute CPU-GPU difference for the same fixed seed.
- **B**: mean absolute difference between two CPU runs with different seeds.
- **Block**: one output layer and source group compared over one pair of seeds; it passes when A/B < 1, so the GPU stays inside the CPU's own run-to-run variability.

## Contents

| Folder | What it holds |
|---|---|
| `figures/` | The three PR figures (PNG and SVG), the script that draws them, and `figure_numbers.json` with the values shown |
| `main_study/` | 448-run study: configuration settings (`configurations.json`), 240 fixed-seed blocks, 480 repeat pairs with the same seed (`repeatability.csv`, all differences 0 in the decoded layer values), native-seed scalars, per-run timing and CPU/GPU speedups |
| `supplement/` | 56-run supplement, two configurations (`true_flat`; `combined_ns2` with two layers, four source groups, three receptors and 4 h on/off emissions): 87 fixed-seed blocks and timing |
| `feature_suite/full_50/` | 50 feature, stress and invalid-input cases, run before the seed and vertical-precision changes |
| `feature_suite/vertical_double/` | Vertical-concentration cases after the double-precision change |
| `feature_suite/vertical_precision/` | Lowest vertical layer before (float sum) and after (double sum) for the 20 highest cells of two cases, same inputs and seed |
| `feature_suite/final_code/` | 18 cases (17 with fixed seeds) re-run after the last kernel and runtime change, without any override switch |
| `native_seeds/` | Native-seed runs: CPU, CPU repeat, a CPU build with the old GPU seeding, the old GPU seeding (`gpu_native_old`), an intermediate TickCount-based GPU seeding (`gpu_native_new` in `native_recheck_report.json`), and CPU and GPU with hashed seeds |
| `final_build/` | Checks of the final PR commit: build log (English, with the commit and command line; `TreatWarningsAsErrors`, 0 warnings); B00 smoke on CPU and GPU against the main-study output, inputzr.dat end-of-run cases, and a vertical-file failure followed by a rerun, all run with that build (DLL SHA256 in each file); the NVRTC compile matrix of the final `generated.cu` |

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
