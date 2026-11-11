# RTX 5080 stability checks, 2026-11-12

Build: PR head `63ce3c6` (the later commit `7dceaf1` changes only documentation). GPU: NVIDIA GeForce RTX 5080, driver 621.14 (CUDA 13.5), NVRTC 12.9. The same checks ran on an RX 9070 XT on 2026-11-11 (PR comment of that day).

| File | What it holds |
|---|---|
| `feature_suite_report.json`, `feature_suite_summary.md` | the 50-case feature suite (CPU and GPU, fixed and native seeds). Same screen per case as on the RX 9070 XT; largest fixed-seed A/B 0.0085 (odour), 0.0032 (concentration) |
| `extra_conditions.json` | two GRAL processes on one GPU, the general kernel, reproducible sums off, a 128 KiB memory budget (transient and stationary), block 256 with chunk 4096, situations 7-12, AVX-512, and three runs with only `INU_GPU_EXPERIMENTAL=1`; each compared byte for byte with the suite's GPU run |
| `cuda_checks.json`, `cuda_checks_plan.json` | 88 runs of the CUDA-path items that had only been compiled or run on HIP (see below) |
| `cuda_checks_2.json`, `cuda_checks_plan2.json`, `cuda_checks_plan3.json` | 28 more runs: kernel time with and without reproducible sums on an idle GPU, memory budgets that place the integer words in host memory, device error 5, startup failures with and without fallback (including the automatic CUDA-to-HIP attempt), an old runtime folder, an invalid pinned budget and a nested log folder |
| `gff_project_repeat.json` | a GUI project with GRAMM terrain, prognostic buildings and a precomputed `.gff` flow field, run twice with reproducible sums on and twice off |
| `scripts/` | the harness copies used for these runs |

`cuda_checks.json`, by key:

- `item1_repeatability`: nine projects (B00 and eight feature cases), each run twice and with chunk 4096 + block 256, chunk 1000, `INU_GPU_MAX_KERNEL_MS=50` and `=0`. All result files are byte-identical within each project, although the launch counts differ (for example 253 against 125,909 launches).
- `item2_b00_float_sums`: B00 with `INU_GPU_REPRODUCIBLE_SUMS=0` gives the same 96 GRZ members as the final448 study run. `item2_atomic_order_control`: with float sums a chunk change alters 48 of 98 files of `wet_drift_all`; with integer sums none.
- `item4_carry`: a carry threshold lowered to 2^34 gives the same bytes; a forced overflow stops the run with the reproducible-sums error.
- `item5_cubin`: `INU_GPU_FORCE_CUBIN=1` (sm_120) gives the same bytes as PTX, with a cache miss and then a hit.
- `item7_9_backend_and_fallback`: backend choice and invalid settings; with `INU_GPU_FALLBACK_ON_STARTUP=1` each tested startup failure runs on the CPU with the CPU's bytes.
- `item11_specialize`: `INU_GPU_SPECIALIZE` is ignored on CUDA. `item15_mixed`: a run that mixes GPU and CPU-fallback situations repeats byte for byte.

Not reproduced: a move of the integer words to host memory during a run. With budgets of 280 to 305 MiB, B00 places them in host memory at the start (same bytes); from 310 MiB they stay in GPU memory.
