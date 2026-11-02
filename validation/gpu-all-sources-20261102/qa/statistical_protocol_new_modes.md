# Statistical protocol for direct GPU POINT, PORTAL and steady execution

Status: predeclared design. This protocol contains no measured result. It applies only to the isolated `20261102_gral_gpu_point_portal_steady` job. Preserve the prior `general_dispatch` source, protocol and outputs.

## Design and scope

Run two cohorts separately: `transient_all_sources` and `steady_all_sources`. Each fixture contains four source groups: SG1 AREA, SG2 horizontal LINE, SG3 POINT and SG4 PORTAL. Compare every group and their sum. Measure elapsed time for the complete mixed-source run. These timings cannot identify the cost of an individual source type.

Both cohorts use a 50 x 50 concentration grid, 20 m cells, origin (2000, 2000), 360000 new particles per situation and 16 workers. Source emissions and meteorology remain constant. Keep the effective affinity on logical CPUs 16 through 31. Launch one model process at a time.

In transient mode, 24/48 situations represent consecutive one-hour intervals with residual-particle carryover. In steady mode, they represent 24/48 steady meteorological situations with a 3600-second reference interval each. Steady situations must not carry transient particles into the next situation. The duration label does not establish a 24/48-hour transient history for steady mode.

The comparison assesses the tested numerical implementation against the CPU reference. Physical validity and general scientific equivalence remain unestablished. This study has no supplied application-specific concentration equivalence margin. CPU seed variability provides an engineering reference, not a universal physical tolerance. Equivalence testing requires a defined margin. See [NIST TN 2106, Section 5](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2106.pdf).

## Frozen allocation

Each cohort contains 22 measured runs, for 44 total:

- Six 24-situation CPU/GPU seed pairs: 12 runs.
- Two additional 24-situation pairs at the base seed: 4 runs.
- Three 48-situation pairs at the base seed: 6 runs.

The seed offsets are 0, 100000, 200000, 300000, 400000 and 500000. For the six seed pairs, alternate CPU/GPU and GPU/CPU order, starting with CPU/GPU. The additional 24-situation pairs use GPU/CPU, then CPU/GPU. The 48-situation pairs use GPU/CPU, CPU/GPU, then GPU/CPU. Complete the transient cohort before the steady cohort.

The first base-seed 24-situation pair also belongs to the timing sample. Count it once. Each mode has six distinct science seed settings and three fixed-seed timing pairs per duration. Fixed-seed repetitions and source groups do not add independent science seeds. Analyze the modes separately.

Use the test-only seed overlay at the designated RNG constructor. Change only the constructor offset. Preserve model time, meteorology and physical inputs. Record actual Seed1/Seed2 values, require CPU/GPU agreement within each pair, and check that different offsets produce distinct states. Check offset 0 against the unmodified CPU build. Different states do not prove independent random-number streams.

## Preparation and timing conditions

Complete an untimed four-situation GPU functional run for each cohort using the final binary and runtime. Both runs must populate the shared PTX cache before measurement. Every measured GPU run must report a cache hit. Preserve the warmup receipts separately from the 44 measured runs.

Before each measured run, require 10 continuous seconds of the harness idle condition. Two consecutive five-second observations define this gate. Preserve the observations and thresholds in the run receipt. An initial 45-second idle check may also precede the first measurement. The earlier study used a 45-second per-run gate. Do not pool its timing sample with this study.

Record three time definitions: process start to exit; observer boundary after situation 3 and its output drain through the final boundary and drain; and each full situation interval. Keep seed-to-end intervals as additional diagnostics. Exclude preparation and the first three situations from the primary steady timing. Retain all situations in the plots and the complete process time.

Separate CUDA-event device time from host wrapper time. Obtain device intervals by differencing cumulative `kernel_device_ms` values for a new server. `fresh_kernel_ms`, `residual_kernel_ms` and `kernel_total_ms` include host launch, synchronization and status reads. They are nested in host roundtrips and must not be added as separate phases.

## Execution and output checks

Freeze the ordered manifest, both protocol files, physical inputs, source, overlay, binary, GPU runtime, NVRTC, validation scripts and analysis scripts before the first measured run. Also bind the warmup receipts and actual seed probe. Root owns this freeze. Check frozen files before and after every run. Preserve failures and stop the cohort when a contract fails. Do not repeat runs automatically or extend the seed sample until a gate passes.

For every situation, require actual GPU dispatch and complete output. Compare the dispatched fresh-particle count with the host count of completed GPU execution requests. In transient mode, compare dispatched residual counts with completed GPU request counts and the host ledger. In steady mode, residual particles, residual batches and device residual work must all be zero. Require a positive CUDA-event interval and an increased kernel-launch counter for each measured situation. Individual single-source functional cases provide source-specific GPU evidence. The mixed cohorts use frozen four-source inputs, positive output in every SG, total completed-request counts, CUDA-event evidence and CPU comparisons. The phase counts are host instrumentation, not counters inside the device kernel. Device counters for individual source types are not measured. Steady execution must also pass the implementation tests that reject transient-only allocation or import.

Check source-group membership, output dimensions, expected situation numbers, finite nonnegative concentrations, input hashes and seed evidence. Restore sparse files to the full 50 x 50 grid using physical cell centers from 2010 through 2990. Preserve zero cells. Reject off-grid coordinates without clipping. Missing evidence produces INVALID rather than a numerical pass.

Use fixed 100 ms process-memory and approximately 200 ms device-memory sampling targets. Report actual intervals. Keep process RSS, private bytes and OS peak working set distinct. Label GPU memory as device-wide unless the measurement API supplies process memory. Application allocation counters are a separate quantity. Preserve missing measurements as missing.

## Metrics and observed engineering gate

The primary science window is situations 4 through 24. Report all 24 situations as a sensitivity view. Use equal cell-area and one-hour weights across the fixed grid. Calculate symmetric weighted NMAE, signed normalized bias, spatial Pearson correlation of time-mean maps, P95/P99, maximum absolute difference and peak locations.

For fields X and Y, define L(X,Y) as their weighted mean absolute difference. Normalize NMAE and bias by [mean(X)+mean(Y)]/2. Quantiles use linear interpolation over the full fixed cell-situation population. Both-zero fields have zero normalized error. A constant map has undefined correlation. For ratio diagnostics, retain 0/0 as undefined and positive/0 as infinite. Do not introduce a data-dependent epsilon.

Use three disjoint prespecified seed-index blocks: (0,1), (2,3) and (4,5). For each block and source-group outcome:

- A = [L(C_i,G_i) + L(C_j,G_j)]/2.
- B = L(C_i,C_j).
- D = L(G_i,G_j).
- R = A/B and V = D/B.

The observed primary gate requires R < 1 in every informative block, for all four groups and their aggregate within each mode. When B=0, A=0 records an exact observed match. Positive A with B=0 fails the gate. The V range [0.5,2.0] is a predeclared engineering review screen, not a physical equivalence margin. Review all bias, correlation, quantile and maximum-difference diagnostics even when R passes.

Report the 15 within-backend seed pairs as dependent diagnostics. Resample the three disjoint blocks together across all outcomes, enumerating the 27 ordered size-three resamples. Report descriptive percentile intervals and their zero-denominator counts. RNG-stream independence and confidence-interval coverage are unverified. Neither a bootstrap interval nor a nonsignificant difference proves equivalence. Paired resampling keeps matched observations together. [SciPy's bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) describes that contract and degenerate distributions.

Use INVALID, engineering_fail, engineering_review_required or engineering_pass_observed_fixture as the engineering decision. Preserve inference_inconclusive, formal_equivalence_not_tested and physical_validation_not_established. A numerical screen cannot supply the final diagnostic review.

## Fixed-seed numerical repeatability and delivery

For both 24 and 48 situations, compare the three CPU/GPU pairs and all three within-CPU and within-GPU pairs. Evaluate every source group and aggregate over all situations and over situations 4..N. Report NMAE, signed bias, mean difference, maximum absolute difference, exact decoded-array equality and the count of different values. These dependent comparisons are predeclared for the new study. They add no independent seed and impose no extra acceptance threshold.

For each mode, deliver the raw timing and memory traces, seed evidence, source-group metrics, fixed-seed comparisons and plots. Report timing median, range, sample SD, CV and the three paired speedups for each duration. Keep 24 and 48 situations separate. Show per-situation time and memory, concentration comparisons, R/V, host pipeline phases, actual CUDA-event intervals and allocation counters. All findings remain bounded to the tested cases and this machine.
