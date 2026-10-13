# Correctness checks at practical particle rates

The baseline is V2701 commit `891225b2f9dbbcda7f5ef6e9ef6db65e64845108`. The candidate adds #66, #67, #70, #74 and #75. These checks exercise normal tracking and the source-group and emission-header fixes at 100, 1,000 and 8,000 requested fresh particles/s.

| Rate | Duration per situation | Sources and groups | Cells | Weather |
| ---: | ---: | --- | ---: | --- |
| 100/s | 60 s | 2 point sources, 2 groups | 20 m | Stable, 0.5 m/s |
| 1,000/s | 120 s | 16 mixed sources, 8 groups | 10 m | Neutral, 1 m/s |
| 1,000/s | 60 s | 108 area sources, 108 groups | 20 m | Unstable, 2 m/s |
| 8,000/s | 60 s | 32 area sources, 8 groups | 40 m | Unstable, 1 m/s |

Every run covers three successive situations in a 200 m square domain, with one worker and fixed seeds. Each supported case compares the baseline with the candidate on the same input, then adds an unused emission column to the candidate input. The two-group case also relabels the selected groups as 101 and 255. The 108-group case compares the candidate's ordinary and extra-column inputs because the baseline cannot load that many selected groups. Each variant is repeated twice.

All 22 executions passed. There were 1,242 byte-identical concentration payload comparisons after equivalent group relabeling. Decoded values were finite and nonnegative, fresh-emission mass matched the expected values at the log's rounding precision, and allocated particle counts matched across equivalent inputs. Both Release builds passed with warnings treated as errors, with zero warnings and errors. The recorded execution times support traceability; this suite checks correctness.

The small-count and injected-fault tests in the earlier PR evidence remain boundary tests. The practical-rate runs here supplement them with normal workloads.

## Reproduce

Use Python 3 and .NET 10, and choose a new scratch directory:

```text
python reproduce.py --work new-scratch
```

Use `--dotnet` to provide an explicit executable path, or `--prepare-only` to verify the included source hashes without building or running. The runner checks all included source hashes before compiling. Engine runs have a 60-second timeout and a ten-minute suite limit. Source files, synthetic input files and measured JSON are included; engine binaries and raw model outputs are omitted.
