# Additional checks for PR #64 with #68 and #69

The final comparison contains 120 GRAL Main executions: six synthetic conditions, four source variants and five repeats. All variants start from V2701 commit `891225b2f9dbbcda7f5ef6e9ef6db65e64845108`. The baseline already includes #59, #60, #61 and #65.

The cases use 3,000 to 100,000 requested particles, 2 to 512 source records, 2 to 64 source groups, concentration grids of 10, 20 or 40 m, and one or nine slices. Five cases use one worker. The concentrated point-source case uses four workers. The terrain case uses a synthetic sloping surface and a prescribed wind field; no GRAMM simulation is involved. Each run starts a fresh process. Variant order rotates between repeats and between cases.

## Results

In the four-worker case, all four baseline comparisons against the first repeat differed, with at most 15 changed cells and a maximum relative cell difference of `1.8655435963301418e-6`. The #64 and #64+#68+#69 repeats had no changed cells. The numerical differences in the baseline were small. These five repetitions do not establish a general guarantee of bitwise repeatability.

The median wall time for #64 in that case was 1.281 s, compared with 1.269 s for the baseline. The median peak process-commit difference was 0.49 MiB. In the 10 m, 64-group, nine-slice case, #64 increased median peak commit by 52.74 MiB. Its median wall time was 1.031 s versus 0.910 s; the individual measurements ranged from 0.937 to 1.114 s and from 0.901 to 1.050 s respectively. See the individual measurements in `results/main_summary.json`.

The combined #68+#69 variant did not reduce median total wall time in these six cases. Its changes ranged from +0.36% to +3.37%. This result does not support a claim that those optimizations offset #64's cost in general. The earlier component timings measure only the changed operations; these timings cover an entire Main execution.

The allocation fixture uses the same jagged-array shape and array builder as #64. A 114 by 82 grid with nine slices and 108 groups allocated 78,891,400 bytes (75.24 MiB), including array and closure overhead. The same 57 by 41 km domain at 250 m, or 228 by 164 cells, allocated 309,114,328 bytes (294.79 MiB). These are allocation-only measurements, not additional process peaks observed in a production run.

The separate precision fixture tests 72 permutations of constructed positive dyadic contributions. Double accumulation followed by one float conversion matched the correctly rounded float reference in every case. The fixture isolates rounding behavior; its input values are not samples from a production run.

## Reproduce on Windows

Use .NET 10, Git and a verified Python executable with NumPy installed. Set `$python` and `$dotnet` to their full executable paths. Start in this directory with no existing `sources` or `reproduction` directory.

```powershell
git clone --single-branch --branch V2701 https://github.com/GralDispersionModel/GRAL.git repo
& $python -X utf8 -B .\prepare.py --repo .\repo
& $python -X utf8 -B .\benchmark.py --dotnet $dotnet --run-dir .\reproduction --repeat 5
& $dotnet build .\component\Component.csproj -c Release -t:Rebuild --nologo /p:TreatWarningsAsErrors=true
& $dotnet .\component\bin\Release\net10.0\Component.dll .\component\reproduced_result.json
```

Source preparation applies the three supplied patches and checks all 340 source-file hashes against the recorded manifest. The four GRAL builds and the component build passed with zero warnings and zero errors. Reconstructing the sources from this bundle passed all 340 hash checks. That check rebuilt the source copies without repeating the performance test.

## Measurements and limits

`results/main_summary.json` contains all 120 wall-time, process-CPU and memory records. Each output digest covers the sorted names and SHA-256 hashes of the decompressed concentration payloads. The public bundle excludes concentration arrays, checkpoints and executables. `results/review_summary.json` and the CSV files provide the comparisons used in the reply.

Wall time includes process startup, JIT, initialization and output. Console dispersion times have coarse rounding and are descriptive only. The recorded `PROCESS_MEMORY_COUNTERS_EX` values were sampled every 10 ms and once after process exit. All 120 final queries succeeded. `PeakWorkingSetSize` and `PeakPagefileUsage` are Windows peak working-set and process-commit counters. `PrivateUsage` is a sampled maximum.

An initial 108-group mixed-source condition stopped in the existing point-source reader, whose emission summary uses `double[101]`. The final Main cases use at most 64 groups. The excluded attempt is recorded separately and contributes no timing results. The 108-group allocation fixture does not exercise the point-source reader. No engine changes were made to work around that input limit.
