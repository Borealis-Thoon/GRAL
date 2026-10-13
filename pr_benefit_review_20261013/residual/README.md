# Residual-policy follow-up

The follow-up supports withdrawing #62 and #63 in their current form. The active-source reference greatly increased residual work when a strong source switched off. The planner removed much of that added work, but the existing V2701 policy still ran faster. No measured accuracy gain justified the change in sampling.

| Condition | V2701 | #62 | #62 + #63 |
| --- | ---: | ---: | ---: |
| 100 particles/s, 60 s, 2 point sources, 20 m, stable | 0.598 s | 0.594 s | 0.601 s |
| 1,000 particles/s, 60 s, 2 point sources, 40 m, source switch-off | 1.276 s | 1.525 s | 1.328 s |
| 1,000 particles/s, 120 s, 16 mixed sources, 10 m, neutral | 1.583 s | 1.613 s | 1.590 s |
| 8,000 particles/s, 60 s, 32 area sources, 20 m, unstable | 1.608 s | 1.645 s | 1.606 s |

Times are medians of five complete engine executions after one warm-up for each variant. Each execution covers three weather situations at the stated duration per situation. The source-switch-off case uses a 99:1 nominal emission ratio: both sources operate in the first situation, then the stronger source stops. Stable cases use 0.25 m/s wind and one worker; the neutral case uses 2 m/s and four workers, and the unstable case uses 1 m/s and four workers. The flat domain is 200 m by 200 m. The other three conditions have overlapping timing ranges.

The configured rates are 100, 1,000 and 8,000 particles/s. The corresponding fresh-particle allocations per situation are 6,000, 60,000, 120,000 and 480,000, exactly matching the requested rates and durations. Source types, source counts, grid spacing and weather vary along with the release rate.

In the switch-off case, residual releases totaled 5,291 with V2701, 494,031 with #62 and 114,626 with #62 + #63. Whole-run time rose by 19.5% and 4.0%, respectively. The concentration fields changed by 2.92% and 2.73% in relative L1 distance from V2701; these are sampling differences, with no independent accuracy reference. The other three conditions produced the same residual split counts across variants.

All 84 executions completed: 60 timed ordinary runs, 12 warm-ups and 12 separately instrumented runs. The instrumented copies measure split counts and residual tracking time; ordinary builds supply the whole-run timings. Fresh-emission mass checks, finite nonnegative concentrations, expected output counts and deterministic serial repeats passed. The maximum relative L1 difference in the other three cases was 9.43e-8. Six Release builds passed with warnings treated as errors, with zero warnings and errors.

The baseline is V2701 at `891225b2f9dbbcda7f5ef6e9ef6db65e64845108`. The #62 topic is `e44523982fb88a8d1cc8929bc650b8b1719be14f`; #63 is `4f7e7415da141af8900eeb785b269550b12bb3b2`, including the one-particle-floor early exit. Each topic patch is applied independently to the baseline. The source manifest records the resulting file hashes.

## Reproduce

Use Python 3 and .NET 10 on Windows. Put a local GRAL clone containing the pinned V2701 commit at `repo`; the included patches supply the topic changes. Run from this evidence directory, with an unused work directory:

```powershell
& $Python residual_benchmark.py --prepare --work-dir work --source-repo repo --template-root template --qa-dir qa
& $Python residual_benchmark.py --execute --work-dir work --qa-dir qa --dotnet $Dotnet
```

`$Python` and `$Dotnet` are the installed executable paths. The runner uses a 60-second limit for each engine execution and a 720-second suite limit. `residual_summary.json` contains all timing ranges, `residual_records.json` contains each run, and `diagnostics.csv` contains the residual counts. Instrumentation does not change the concentration payloads in the serial cases.
