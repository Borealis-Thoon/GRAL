# Follow-up review of PRs #66 and #67

This folder records the review after the V2701 merges of PRs #59, #60 and #61. The comparison baseline is upstream commit `324dd08161bb2a4a4d02a43f33e2a7f4ebd0eff7`.

The #66 conflict was resolved by keeping the non-finite mass check before the bounded residual split calculation. PRs #62 and #63 received upstream history merges; their complete source trees remained unchanged. PR #67 merged cleanly. The revised branches preserve upstream residual seeds and the bounded split calculation. No additional defect was found in either guard implementation.

## What was checked

The normal-input Main suite compared upstream, #66 alone, #67 alone and the two guards together. All **160 Main executions and 2,528 checks passed**. The suite used 18 synthetic conditions, two fixed-seed repeats, 100 to 3,000 particles and 10, 20 or 40 m concentration grids. It included steady and transient tracking, mixed source types, deposition, receptors, odour slices, buildings and synthetic terrain. All **1,140 output payload pairs in the 108 normal baseline/candidate run comparisons matched**. Repeat and restart comparisons were checked separately; eight executions read a saved checkpoint successfully.

These Main comparisons use one worker. They check compatibility with upstream under the selected normal conditions. They do not measure a production speedup, atmospheric accuracy or full-run behavior under injected faults. Faults and multiple workers are covered separately by the component tests below.

| Component check | Passed checks | Scope |
|---|---:|---|
| Shared guard regression | 1,917 | Actual initial driver and storage calls; freshly extracted tracking, decay, wet-deposition, receptor-exit and reporting blocks |
| #66 state boundaries | 98,325 | 98,304 state classifications with an independent IEEE exponent-bit check, atomic counts at 1, 2 and 8 workers, and 18 residual-entry cases |
| #67 storage boundaries | 16,314 | 8,080 finite signed-mass output comparisons, invalid increments, overflowing sums, existing non-finite cells and concurrent writes |
| #62 active reference | 10 | Reference mass from active source rates and the fallback when sources are off |
| #63 adaptive target | 62 | Split thresholds, target limits, cancellation and floating-point mass-splitting behavior |

A rejected particle loses its remaining contribution; prior valid contributions remain. The storage guard leaves a rejected destination unchanged and does not repair a cell that is already non-finite. Finite invalid indices, malformed geometry and other concentration or deposition accumulators remain outside these patches.

## Source versions

| Variant | Tested commit |
|---|---|
| Upstream | `324dd08161bb2a4a4d02a43f33e2a7f4ebd0eff7` |
| #62 | `e44523982fb88a8d1cc8929bc650b8b1719be14f` |
| #63 | `370084ba3d933e8cf444b33af93a34db41ba91fe` |
| #66 | `cf09cb2b0af9f5a96ee97de4f060f1c4d5161437` |
| #67 | `4b8f5e98f63d4a6d0768a1114b357874ec16ead3` |
| #66 + #67 review composition | `4690ee84e859e626066969f543bb7b36a47ded91` |

The last commit identifies a local review composition. Its complete patch against upstream is provided; reproduction does not require that commit to exist on GitHub. The composition retains both independent counter reports in `Program.cs`.

`source_manifests/variants.json` records SHA-256 hashes for the 85 build-source files in each variant, using LF line endings. The original review records also include hashes of local tracked editor settings, which are outside the 85-file build set. Five patches reconstruct all candidate variants from the single upstream commit.

## Reproduce

Use Git, a verified Python 3 installation and the .NET 10 SDK. In these examples, `python` stands for the verified interpreter on your machine. On Windows, check that it resolves to an installed interpreter rather than a Microsoft Store alias. Use fresh destination and run directories.

From this folder:

```text
python -B reproduce/prepare_sources.py --destination ../prepared
python -B reproduce/run_components.py --package-root ../prepared --run-dir ../component_run --dotnet dotnet
python -B ../prepared/reproduce/run_main.py --package-root ../prepared --run-dir ../main_run --variants nan_guard_state nan_guard_storage nan_guard_combined --scope-file ../prepared/inputs/scopes.json --repeat 2 --execute --dotnet dotnet
```

`prepare_sources.py` clones the public upstream repository, reads the pinned baseline, applies the included patches and checks all 510 source hashes. `--repository` can select an existing local clone that contains the baseline commit. The component runner verifies those prepared sources again, regenerates the extracted guard blocks, checks them against the supplied copies and performs nine strict Release builds with warnings treated as errors. Each test runner has a 15-minute limit and terminates only the processes it starts on a timeout.

The source reconstruction and component commands were executed for this package. They passed with the counts above and zero build warnings or errors. The Main scripts and synthetic templates are the same files used for the recorded 160-run suite; that full suite was not repeated solely for packaging.

## Files and limits

- `qa/main_validation_summary.json` and `qa/main_output_comparison.csv` contain the Main results. `qa/component_reproduction.json` records the public component runner's own execution.
- `qa/pr66_review.json`, `qa/pr67_review.json`, the residual review files and `qa/final_source_cross_review.json` document the code review and merge decisions.
- `logs/` contains strict-build records. Local job roots in published records are replaced with `${REVIEW_JOB}` or `${PRIOR_JOB}`.
- `inputs/template/` and `reproduce/main_inputs.py` define synthetic inputs only. Raw model outputs, checkpoints, executable binaries and caches are excluded.
- `MANIFEST_SHA256.json` covers every published file except itself. The included engine patches and extracted engine blocks retain the upstream GPLv3 terms in `License.md`.

Earlier figures remain valid for their stated source versions and conditions. This follow-up adds compatibility and boundary evidence without assigning new performance or accuracy claims to those figures.
