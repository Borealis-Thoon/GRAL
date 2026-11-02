# GRAL GPU general-dispatch bounded validation protocol

Status: PREDECLARED DESIGN. This file reports no model results.
Owner: statistical-protocol agent. Scope: this file and statistical_protocol.json only.
Freeze both files and record SHA256 before the first measured run. Record any later amendment, its reason, and whether outcomes had been inspected. Do not tune gates after inspecting results.

## 1. Question and claim boundary

Test whether AREA and two LINE geometries use the GPU correctly, whether unsupported situations use the complete CPU path, and whether GPU discrepancies are smaller than CPU seed-to-seed Monte Carlo variation in the tested virtual fixture. Measure repeatability, elapsed time, and memory on this machine.

The primary fixture contains AREA, horizontal LINE, and vertical LINE, with a separate source group for each. A situation with any unsupported source uses whole-situation CPU fallback. Therefore, do not mix unsupported sources into the main GPU performance fixture.

This is a bounded engineering comparison against the CPU implementation. It cannot establish atmospheric validity, agreement with observations, equivalence for every GRAL configuration, or a universal acceptable concentration error. No application-specific physical equivalence margin has been supplied. A nonsignificant difference is not evidence of equivalence. NIST TN 2106, Section 5, explains equivalence tests through a defined indifference zone: https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2106.pdf

The CPU Monte Carlo scale is a reference, not a scientific tolerance. Different backends can use different random-number sequences even when their input seed matches. Failure of the same-seed gate requires investigation; it does not by itself prove that a backend is physically wrong.

## 2. Fixed execution contract

- Isolate runs under this job. Preserve production engines, input packages, and active processes.
- Use the same 16 allowed logical CPUs for both backends. Record the effective affinity mask, process priority, configured worker count, CPU model, GPU model, driver, binary hash, and relevant environment. Do not alter Process Lasso or system-wide scheduling.
- Freeze all model inputs, grid, particles, emission rates, source geometry, meteorology, concentrations, output groups, and boundary settings. The expected fixture uses a 50 x 50 grid and 360000 new particles per model hour; verify these values from the actual fixture before accepting the cohort.
- Within the 24h science cohort, only the seed offset changes. Within a CPU/GPU pair, only backend selection and output paths may differ. The 48h timing cohort changes duration only and is reported separately.
- Fixed offsets: 0, 100000, 200000, 300000, 400000, 500000. Base offset is 0.
- The test-only overlay may pass checked(IWET + offset) to the designated RNG constructor. It must not change meteorological selection, model time, output numbering, source inputs, or shared state. Do not change a readonly Seed field after initialization.
- Record the effective Seed1/Seed2 state or sufficient exact initialization evidence for every constructor call. Verify CPU/GPU matching within each seed and differences across offsets. Check arithmetic range and the actual constructor's shift/overflow semantics. If seeds are unchanged or actual seed identity is unverified, mark seed-control INVALID and do not interpret the seed cohort.
- Prove the overlay's offset=0 behavior matches the unchanged build on a short fixture. Keep overlay changes and production dispatch changes separate in the evidence.
- Execute one model process at a time. Do not overlap timed pairs. Preserve failures; do not silently replace or select the fastest repeat.

## 3. Run allocation and fixed order

Measured main runs: 22 total.

1. Six 24h CPU/GPU seed pairs: 12 runs. Offsets follow the fixed list above. Order is CPU/GPU for offset indices 0, 2, 4 and GPU/CPU for indices 1, 3, 5.
2. Two additional 24h base-offset pairs: 4 runs. Orders GPU/CPU, then CPU/GPU. Together with the base-offset science pair, each backend has three 24h timing repeats.
3. Three 48h base-offset pairs: 6 runs. Orders GPU/CPU, CPU/GPU, GPU/CPU. Each backend has three 48h timing repeats.

The first 24h base-offset pair participates in both analyses, but it is one observed pair. The extra fixed-seed timing repeats do not increase scientific n. Scientific n=6 seeds. Independent disjoint seed-pair blocks n=3. Timing n=3 pairs per duration. Do not pool 24h and 48h repeats.

Use an untimed preparation pass to create required caches and establish the declared warm-cache condition. Retain its elapsed time and logs separately. Do not count preparation as a measured repeat. If no preparation pass is performed, preserve cold/warm labels and do not combine them as one timing condition. Declare first-three-situation exclusion before analysis; never choose the excluded prefix from the observed trace.

Separate short functional matrix: 4h or the minimum meaningful duration for each case. Include AREA-only, horizontal LINE-only, vertical LINE-only, a supported mixed case, POINT, PORTAL, an unsupported-plus-supported mixture, and relevant guard-triggering configurations present in the implementation. Compare each fallback case against explicit CPU mode using the same inputs and seed. Record the intended dispatcher reason and actual backend evidence. Short functional runs are additional to 22 measured runs and do not contribute to science/timing n.

## 4. Required output integrity

Before metrics, verify expected files, source-group mapping, time/situation mapping, concentration shape, nonnegative finite values, completion status, actual backend counters, and model/input hashes. Decode identical output cells for both backends. Missing expected output, NaN/Inf, unexpected negative values, incorrect source dispatch, or unverified seeds makes the affected cohort INVALID. Record the defect instead of substituting zero. A fallback run must demonstrate CPU work and zero GPU-dispatched situations, not merely a successful process exit.

Verify output invariants and any deposition/particle accounting available in the engine. Concentration sums are concentration summaries, not total emitted mass or proof of mass conservation.

## 5. Scientific outcomes and sampling units

Primary window: situations/model hours 4 through 24 inclusive for the 24h cohort. Also report all 24 hours as a declared sensitivity view. Hour 1 through 3 exclusion primarily defines the timing comparison; the sensitivity view prevents it from hiding startup discrepancies. The fixture must map one situation to one model hour; if it does not, document the actual mapping before evaluation.

Evaluate each source group and their aggregate. Use identical fixed spatial support and cells for every run. For cell/hour k, use w_k=cell_area * output_interval; constant weights reduce to equal weights. Preserve zeros. Do not select cells by GPU concentration. For maps, first form the time-weighted mean at each cell.

For nonnegative fields X,Y, define M(X)=sum(w*X)/sum(w), L(X,Y)=sum(w*abs(X-Y))/sum(w), and symmetric reference mean S(X,Y)=(M(X)+M(Y))/2.

Required metrics:

- weighted NMAE = L(X,Y)/S(X,Y). Use this symmetric version for same-seed and different-seed comparisons. Do not call an unweighted mean of cellwise relative errors NMAE.
- signed normalized bias = (M(Y)-M(X))/S(X,Y), GPU minus CPU for backend pairs; also retain absolute concentration difference M(Y)-M(X).
- spatial Pearson correlation of time-weighted mean maps. Report coefficient, not a cell-level significance test. Constant maps have undefined correlation; return null with reason.
- P95 and P99 of the fixed cell-hour concentration population; use a fixed linear-interpolation quantile algorithm. Report raw values, signed GPU-minus-CPU differences, and absolute differences. If all cells/intervals are equally weighted, ordinary quantiles apply; otherwise implement weighted quantiles consistently and record the method before evaluation.
- maximum absolute concentration difference, and the CPU/GPU maximum concentration with its location. Treat maxima as diagnostics, not a single universal accuracy limit.
- optional hotspot overlap at the CPU P99 threshold, with a predeclared tie rule. Report as exploratory if threshold ties or sparse nonzero support make it unstable.

Zero cases: if S=0 and both fields are identically zero, NMAE=0 and normalized bias=0 with status both_zero. If a reference denominator is zero and its numerator is positive, return infinity plus a reason. Never add a data-dependent epsilon or turn undefined correlation into 1. Report zero-field groups separately from positive-field agreement.

Cells, particles, and hourly outputs within one run are dependent observations. They do not increase the independent seed count. All 15 unique CPU seed contrasts are useful descriptive comparisons; they are not 15 independent replicates. SciPy documents paired resampling as resampling corresponding indices together: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html

## 6. Predeclared engineering gates and decisions

Use three nonoverlapping blocks of seed indices: (0,1), (2,3), (4,5). Fix these before results. For every group and the aggregate, calculate:

A_b = [L(C_i,G_i)+L(C_j,G_j)]/2.
B_b = L(C_i,C_j).
D_b = L(G_i,G_j).
R_b = A_b/B_b; V_b = D_b/B_b.

Common weights and units make R a directly interpretable error-to-CPU-variation ratio. Using raw L here avoids changes in concentration normalization across pair types. Also report weighted NMAE for each underlying pair.

Primary observed gate: every informative block in every required group and the aggregate must satisfy R_b < 1. This implements the stated engineering objective: average same-seed backend error below the CPU different-seed contrast in every prespecified block. This is an observed fixture gate, not a 95% population equivalence test. Report all R values and the worst block; do not hide a failing group behind aggregate agreement.

CPU reference B_b=0: A_b=0 is an exact observed backend match for that block; A_b>0 fails the reference gate. If all CPU contrasts are zero, report exact-match status or failure, and label the Monte Carlo comparison uninformative.

Dispersion diagnostic: V_b in [0.5,2.0] is a predeclared broad engineering screen. This factor-of-two band is a design choice, not a literature-derived scientific margin. Any informative block outside the band gives dispersion_review_required; it prevents the final status engineering_pass until its cause is documented. If B_b=D_b=0, use uninformative_zero, not an invented ratio. Report median, minimum, and maximum for all 15 GPU/CPU same-index seed-pair dispersion ratios as secondary dependent diagnostics.

For normalized bias, spatial decorrelation (1-r), P95, and P99 absolute differences, show the same-seed backend discrepancy beside the CPU interseed contrast for each block. These are mandatory diagnostic outputs, not additional silently optimized acceptance thresholds. A systematic sign, negative values, missing plume, or gross high-tail mismatch requires explicit review even if the L gate passes. Record any review conclusion and its evidence.

Decision fields:

- INVALID: contract, seed control, dispatch, output integrity, or expected measurements are missing/incorrect.
- engineering_fail: at least one informative primary R_b >= 1, or nonzero backend error with zero CPU reference.
- engineering_review_required: primary observed gate passes, but dispersion screen or mandatory diagnostics require explanation.
- engineering_pass_observed_fixture: integrity passes; all primary block gates pass; dispersion is in the declared band or all-zero uninformative; mandatory diagnostics have no unresolved defect. Scope is exactly the tested fixture and configurations.
- inference_inconclusive: report alongside an observed pass when the small seed cohort cannot support a strong population statement. Do not collapse it into engineering_fail.
- physical_validation_not_established and formal_equivalence_not_tested: always report for this task.

## 7. Uncertainty without pseudoreplication

Report all six seed metrics and all three independent block values. Estimate the ratio of means R=sum(A_b)/sum(B_b), and V=sum(D_b)/sum(B_b), over the three independent blocks. Bootstrap whole blocks with replacement, carrying A/B/D and all source groups together. Enumerate all 3^3=27 ordered resamples exactly; use percentile 2.5%/97.5% endpoints and a one-sided upper 95% endpoint as descriptive bootstrap intervals. Keep zero-denominator outcomes explicit. These discrete, n=3 bootstrap intervals are exploratory and do not have established 95% coverage for this fixture. Do not use them as a formal pass certificate.

Optionally compute the exact one-sided sign-test probability for R_b<1 over the three independent informative blocks. With all three below 1, the smallest unadjusted probability is 1/8=0.125 under independent equal-probability signs. Thus this design cannot meet a 5% one-sided sign test even in its best outcome. Report this limitation directly. Do not treat the 15 overlapping seed pairs as independent to obtain a smaller probability. Additional source groups are multiple outcomes, not extra seed replicates.

Do not use failure to reject a difference, a narrow cell-based CI, or a bootstrap interval from three blocks as proof of scientific equivalence. Degenerate bootstrap distributions may produce undefined BCa bounds; do not replace them with a fabricated confidence interval. The explicit percentile enumeration here is chosen for auditability, with its small-sample limitation exposed. SciPy documents bootstrap degeneracy: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html

## 8. Timing and memory outcomes

Keep separately for each measured run:

1. End-to-end process wall time: process start through successful exit, including initialization, cache checks, GPU preparation, output writing, and shutdown.
2. Model-reported per-situation wall times, with raw logs and exact parsing rules. Primary steady comparison uses situations 4..N. Report their sum and median.
3. GPU preparation/JIT/upload time and kernel/device time only if directly measured; retain missing as null. Never infer kernel time from process wall time.
4. CPU process working set/RSS and private bytes; sample at a fixed 100 ms interval if overhead is acceptable. Retain the actual timestamps and sampling interval. Record OS lifetime peak working set, where available, separately from sampled peak.
5. Device-wide GPU memory used and idle baseline using one fixed monitor; sample at 100-250 ms if supported. Label it device-wide and record other GPU activity. Do not report device-wide memory as process VRAM. Report process GPU memory only if the API actually provides it on this Windows configuration. Application allocation counters are separately labeled and are not physical VRAM measurements.

For each duration, show the three raw paired repeats, median, minimum, maximum, sample SD, and CV for each backend and each elapsed-time definition. Report the three paired CPU/GPU speedups and their median/range. Timing repeats are scheduling repeatability on one machine, not independent hardware samples. Do not claim a precise population confidence bound from three timing pairs.

Plot per-situation time versus situation/model hour, all three repeats as faint lines and the median as a strong line. Shade the first three situations and label their exclusion from the steady statistic. Show separate 24h and 48h panels. Plot aligned process memory versus wall time and sampled memory per situation where timestamps permit. Keep RAM, private bytes, and device-wide VRAM in separate panels with units. If situation boundaries are unavailable, do not invent a per-situation memory alignment.

Also plot CPU/GPU concentration maps and difference maps with shared scales, all seed-level metrics, the three primary R blocks, and CPU/GPU interseed dispersion. Mark zeros, undefined metrics, and excluded/invalid runs visibly. Do not place CPU fallback runs in the supported-GPU speedup summary.

## 9. Stop, correction, and delivery rules

If a functional guard fails, fix the implementation before the main cohort. If a measured run fails for an external cause, preserve it, document the cause, and repeat the whole affected pair once; show both attempts. A code/input/seed-control change invalidates comparability with earlier runs and requires a new cohort or an explicitly separate analysis. Do not extend seeds opportunistically until a gate passes.

Deliver the frozen protocol/hash, ordered run manifest, input/binary hashes, seed initialization evidence, dispatch evidence, raw metrics, timing/memory traces, plots, and decision fields. Summarize the actual scope, n, warm/cold cache state, exclusions, failures, missing telemetry, and unresolved scientific limits. A completed bounded assessment may end with observed engineering pass and inference inconclusive; this is a valid result, not a reason to invent stronger evidence.
