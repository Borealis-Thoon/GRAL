# Checkpoint observations outside the SG patch

The additional restart checks exposed two behaviors in the existing checkpoint-writing path. The six-line source-group patch leaves that code untouched. These observations are retained separately so that the narrower OFF-condition test is not mistaken for general uninterrupted/restart equivalence.

## Last checkpoint at process exit

A patched 108-group run completed two situations and wrote both concentration archives. Its checkpoint directory contained an older valid file and a zero-byte final file. `Program.cs` joins the result-output writer before exiting but does not join `ThreadWriteConz4dFile` there. The file metadata and hashes are in `sg_limit_observations.json`; the corresponding core and console logs are in `logs/last_checkpoint_108_*`.

This outcome was observed in the patched run. The unmodified engine cannot complete the same 108-group input, so no identical baseline reproduction is claimed.

## Cumulative emissions during a checkpoint write

An unmodified two-group run produced a checkpoint marked as situation 2. For SG99, the two-situation emission total should have been 0.0125 kg. On loading that checkpoint, the engine reported 0.0141 kg, rounded by its normal log formatting. The four-situation resumed total was 0.0225 kg; the input factors imply 0.020833333333333332 kg. The log is retained as `logs/baseline_concurrent_emission_snapshot_*`.

The writer reads the live `EmissionPerSG` array. The next situation can add emissions before the main thread joins that writer. The observation supports a separate review of that synchronization path.

## Scope of the completed restart test

The completed 12-run test uses a single emission pulse followed by zero emissions. It writes a checkpoint at situation 2, calculates situation 3 so the existing writer is joined, then resumes situations 3 and 4 from that completed checkpoint. This checks SG indexing, stored values, output entries and execution after reload without concurrent additions to the emission counter.

Baseline and patched two-group outputs matched. The 108- and 255-group patched runs also matched their fixed-seed repetitions. In the 255-group resumed window, SG30 and SG224 had zero surface concentration; all group output entries were present and finite, and the total concentration remained positive. A requirement for every group to remain positive after emissions stop would not be an appropriate correctness test.

The initial 30-second sparse-line watchdog attempt and the seven exploratory restart executions remain in the observation receipt. They are excluded from the 96 primary and 12 completed restart executions. The primary table itself contains no watchdog timeout; its baseline failures are 14 exception exits and 10 early exits with code zero. Completion markers and output checks, rather than exit code alone, determine success.
