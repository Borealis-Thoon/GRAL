# Parallel concentration transfer

The double accumulator in PR #64 is copied to the float output array and cleared after each weather situation. The existing transfer walks every column on one thread. On a large output grid, this leaves an independent array pass running serially after the particle work has finished.

This patch assigns columns to the existing worker pool. Each output value is still cast once from double to float, and its double accumulator is then set to zero. Columns have separate storage, so the transfer adds no change to summation order. Single-worker runs and arrays with fewer than 131,072 values use the serial loop. That cutoff is a conservative way to avoid launching parallel work for small arrays; it is not an optimum for every processor. An empty slice set also keeps the original no-op behavior.

The patch changes one file: 16 added lines and one removed line, or 635 added/removed source characters including indentation and excluding line endings. It is based on PR #64 applied to development commit `891225b2f9dbbcda7f5ef6e9ef6db65e64845108`.

## Results

The final source passes strict builds with no warnings or errors. The compiled-method fixture checks exact float bits and cleared double values, including signed zero, NaN and infinity. It covers three empty-slice configurations and 12 size/worker configurations, including 129,024 and 131,072 values on either side of the cutoff. Each timed process warms the actual method for at least 750 ms, then records 15 batches of five transfers. Reported medians omit the first two batches. Allocation and filling are outside the timed interval.

For the 116 × 84 × 9 × 108 array, median transfer time fell from 6.98 to 3.13 ms with four workers and from 6.92 to 1.58 ms with 24 workers. For the 230 × 166 × 9 × 108 array, it fell from 31.61 to 13.35 ms and from 29.43 to 11.87 ms, respectively. The first two dimensions include the allocated boundary cells. These are transfer-stage measurements on one host. The serial fallback still shows small JIT/layout timing differences, and the measurements do not establish an overall model speedup.

Six final-source Main runs compare a dense output grid with four workers, using three interleaved repeats per engine. Every decompressed concentration payload matches the PR #64 baseline byte for byte. An earlier version of the size guard also passed 36 Main runs covering point, area and mixed sources, terrain, dense grids and one/four workers. Those records are retained separately because the empty-slice guard was corrected afterward. No particle-loop or transfer arithmetic changed in that correction.

## Reproduction

Requirements: Windows, .NET 10, Git, and Python with NumPy. Use a local GRAL repository containing the base commit above. The preparation command reads that repository and creates separate source copies; it does not edit the checkout.

```text
python prepare.py --repo <local-GRAL-repository>
python build.py
python validate_transfer.py
python validate_main.py --dense-only
```

`prepare.py` applies the bundled PR #64 patch, copies the candidate file for the second variant, and verifies all 170 source-file hashes. `validate_transfer.py` invokes the private compiled transfer method through a delegate. `validate_main.py` creates synthetic inputs and checks successful termination, finite nonnegative concentrations and payload equality. Run it without `--dense-only` to repeat the five broader Main conditions on the final source.

`results/transfer_results.json` and `results/transfer_summary.csv` contain the final method measurements. `results/main_results.json` contains the final Main comparison. The earlier Main checks are in `results/main_regression_before_empty_slice_fix.json`. Raw model outputs and execution binaries are not included.
