# GRAL PR benefit review at practical particle rates

This follow-up tests whether the proposed changes provide a useful benefit under practical release rates. It covers the 13 PRs that were open at the start: #62, #63, #64 and #66 through #75. The test sources use V2701 commit `891225b2f9dbbcda7f5ef6e9ef6db65e64845108` as their base.

The review recommends closing #62, #63 and #69. The residual-policy changes increased work when a strong source stopped, without an established accuracy gain. Reusing vertical-search results reduced lookup calls but did not improve whole-engine runtime. The other PRs retain measured performance, allocation, precision or correctness benefits.

| Evidence | Runs | Main result |
| --- | ---: | --- |
| [Residual policies](residual/README.md) | 84 | #62 added 19.5% runtime in the source-switch-off case; #63 still added 4.0% against V2701 |
| [Particle-loop changes](hotloops/README.md) | 96 | #69 was slower in all four medians; #68 reduced peak memory in nine-slice cases; #72 reduced runtime in unstable conditions |
| [Optional worker buffers](worker_buffers/README.md) | 86 | Three workloads saved 36.6% to 51.0%; a 16 MiB budget avoided the large dense-grid allocation |
| [Correctness at practical rates](practical_regression/README.md) | 22 | Fresh-emission mass passed and 1,242 equivalent concentration payload pairs matched |
| [Accumulation precision figure](precision/README.md) | Earlier measurements | Small-increment retention and repeated-run agreement explain #64's purpose |

The new suites completed 288 engine executions and 14 strict Release builds with zero warnings and errors. Ordinary performance measurements use five interleaved repetitions after warmup; diagnostic copies are separate. The worker-buffer suite also includes three timed #64-only references per field and a separate six-run budget-fallback check. CPU benchmarks ran sequentially.

Requested release rates were 100, 500, 1,000 or 8,000 particles/s. Durations ranged from 60 to 300 seconds, with source count and type, grid resolution and weather changing across cases. The result files record configured rates and actual particle allocations. The original 100,000- and 1,000,000-particle labels referred to totals over a situation; the new figures show the rate and duration directly. The earlier low-count and injected-fault cases remain boundary tests, with practical-rate regressions added here.

Each folder includes measured results, synthetic inputs and reproduction instructions. The engine implementation was unchanged during this follow-up. No research input, raw model output, checkpoint or executable binary is included.
