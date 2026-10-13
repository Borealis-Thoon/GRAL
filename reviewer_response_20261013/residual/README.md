# Residual particle policy tests

These tests compare V2701 at `891225b2f9dbbcda7f5ef6e9ef6db65e64845108`, that source with #62, and that source with #62 plus #63. The PR implementations are unchanged. The extra diagnostics run in separate copies and are excluded from the reported end-to-end timings.

Twenty synthetic conditions cover 10, 20 and 40 m grids, point/line/portal/area sources, two or eight source groups, and requested particle budgets of 100, 1,000 or 3,000. There are 180 unmodified Main runs and 60 diagnostic runs. Each condition has five 30-second situations in a 200 m square domain. Most cases use stable, low-wind conditions (0.25 m/s, stability class 6) to retain particles; four cases use neutral 2 m/s or unstable 1 m/s conditions. The time labels select emission records; they do not represent hour-long integration.

The engine allocates a minimum number of particles to each source. Actual allocation was 100, 119, 640, 1,000, 1,009, 3,000 or 3,008, depending on the case. Both requested and actual counts are retained in the results. The #63 target is still `TAUS * TPS`, which can be smaller than the actual allocation.

All runs completed with finite, nonnegative concentration outputs and the expected cumulative fresh emissions. The six builds passed with warnings treated as errors. A separate audit checked 255 source hashes, 3,480 concentration payloads, 546,000 float values and the actual meteorology of all 240 runs. In the 19 conditions configured for one worker, all 57 diagnostic/unmodified pairs and 114 repeat pairs had identical concentration payloads. One condition was also configured for four workers; those runs are reported separately and are excluded from the required byte-equality checks.

## Findings

Thirteen conditions produced identical concentrations across all three variants. In those conditions, #63 performs an extra planning scan without reducing the child count. Changes in positive emission factors alone do not change #62's reference mass: it sums the nominal rates of sources whose current factors are positive. When all sources are off, it falls back to the original nominal reference.

The strongest change came when a source with 99 times the nominal emission rate of the other source was switched off while its particles remained. With a 10 m grid and 3,000 actual particles, the cumulative number of residual children was 976 in the baseline, 52,975 with #62 and 11,281 with #62 plus #63. Median end-to-end times were 0.367, 0.389 and 0.374 seconds. At the first off-source situation, all three variants saw the same retained input; the child count was 305, 13,946 and 2,728, respectively. The average scaled mass per child therefore fell from 104.81 to 2.292 with #62 and 11.718 with #62 plus #63. This describes particle weights, without establishing an accuracy improvement.

For that same case, normalized concentration L1 differences from the baseline were 19.70% and 21.37% over all five situations. Excluding the unchanged first situation, they were 103.89% and 112.75%. The denominator is the baseline concentration sum over the selected situations. There is no independent accuracy reference, and the fixed-seed repeats do not measure sampling uncertainty.

A 10 m case with 32 point sources and eight groups requested 100 particles but received 640 because of the source minimum. Each of the four residual situations already had one child per eligible entry, and each had more than 100 eligible entries. All variants released the same cumulative 3,031 children. #63 still performed its bounded adjustment loop, with no child-count or concentration benefit. This is a direct case for stopping when no further split reduction is possible.

These fresh-process runs take fractions of a second, so startup, input/output and timing scatter account for much of the wall time. The three repeats use a cyclic variant order. Diagnostic scans also warm caches; their planner and trajectory times must not be used directly as a production break-even threshold.

## Proposed selection policy

Keep the current nominal-reference behavior as the default and evaluate an explicit Auto mode separately. A source being off is insufficient reason to discard it from the reference mass while its residual material remains. A conservative Auto mode would retain the historical reference whenever an inactive group still has a residual entry above the existing concentration threshold, and record the selected reference in the log.

For planning, estimate both eligible entries and predicted children. If every eligible entry already produces one child, repeated scans cannot reduce work. If the predicted child count is within the chosen target, keep the existing split. Otherwise, use deterministic count limits to bound the additional trajectory work. Keep elapsed-time measurements out of the switching rule so machine load cannot change the selected policy. The entry count is a lower bound on the achievable target. An entry count above the target alone is not a reason to skip planning: a large number of additional splits may still be removable. The log should show the reason for the decision, the target, the eligible-entry floor and predicted children.

The resource measurements support testing this policy. They do not establish a universal threshold or justify turning it on for every simulation. An accuracy claim would require independent-seed ensembles or a suitable high-particle reference for the switching cases.

## Reproduction

Use Python 3 and .NET 10. On Windows, select a verified Python executable. All input fields are synthetic. The commands below use a fresh directory; the harness refuses to reuse a run directory.

```powershell
git clone https://github.com/Borealis-Thoon/GRAL.git gral-source
git -C gral-source fetch https://github.com/GralDispersionModel/GRAL.git V2701
python residual_benchmark.py --prepare --source-repo gral-source --work-dir benchmark --template-root template
python residual_benchmark.py --execute --work-dir benchmark --qa-dir benchmark/qa
python residual_benchmark.py --execute --weather-only --reuse-builds --run-name weather_run --work-dir benchmark --qa-dir benchmark/weather_qa
python residual_benchmark.py --execute --floor-only --reuse-builds --run-name floor_run --work-dir benchmark --qa-dir benchmark/floor_qa
python summarize_residual.py --work-dir benchmark --base-qa benchmark/qa --weather-qa benchmark/weather_qa --floor-qa benchmark/floor_qa --output-dir benchmark/summary
```

Pass `--dotnet` if the SDK executable is not on the command path. Before interpreting a rerun, compare the generated `source_manifest.json` with the included manifest. The two included patches are the exact topic diffs used on the stated baseline. Build logs replace the local work-directory prefix with `<work-dir>`; the counts and build results are unchanged. Raw model outputs, checkpoints and compiled binaries are excluded from this package.
