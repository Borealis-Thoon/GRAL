# C# validation addendum: seed probe and observer

Scope: read-only review of validation/seed_probe/Program.cs and SeedProbe.csproj, validation/benchmark_repo_v2/src/BenchmarkTelemetry.cs, and the benchmark Program.cs diff against repo/src/Program.cs. No build, test, or model execution was performed during this review. Frozen validation files were not edited.

Decision: Approve the reviewed harness delta. No actionable CRITICAL, HIGH, or MEDIUM issue found.

Seed handling:
- The only seed-offset use in model code is the checked constructor argument IWET + benchmarkSeedOffset at Program.cs:681. IWET itself is not assigned the offset. Weather lookup, time-series indexing, result filenames, completion numbering, and telemetry retain the actual IWET.
- Offset parsing uses invariant unsigned-decimal syntax and rejects values outside 0..500000. The default is zero. At the validated situation range 1..48, integer additions and RNG shifts stay within range.
- The probe loads the requested assembly and invokes the actual nested DeterministicRandomGenerator constructor. It does not invoke GRAL Main. The project has no model project reference or extra package dependency.
- For wind speed 2 and direction 0, the independent expected seed formula matches ProgramDeclarations.cs:1374-1375. Each offset is checked at 48 situations, yielding 288 actual-constructor checks. Distinct first-situation state pairs across the six offsets are checked explicitly. The chosen nonoverlapping offset intervals also yield distinct pairs throughout these checked situations. No claim of statistical stream independence follows from these checks.

Timing observer:
- The observer receives scalar copies. It does not write model fields, modify arrays, or change seed state. Its mutable counters and timestamps are private observation state.
- Completion is recorded after the normal receptor and flow-field output calls. Output drains occur only at situation 3 and the requested final situation (4, 24, or 48). The supplied action joins the GFF, GRZ, and Conz4d writer threads without clearing references, changing output data, or replacing the existing later joins.
- The start timestamp follows the warmup drain; the stop timestamp follows the final drain. Intermediate asynchronous overlap remains unchanged. This intentionally changes scheduling at measurement boundaries, not model equations or forcing.
- The measured interval is the post-warmup situation interval with boundary output drains. It excludes GPU close and final program cleanup after FinishGral; it must not be labeled total process elapsed time. Observer file I/O overhead is included in the observed interval.
- Contiguous seed/completion checks reject missing or reordered situations. Finish emits incomplete unless the final boundary was reached. The runner must still check process success because Finish is called before GPU close and final cleanup.

Evidence limits:
- Read qa/harness_seed_probe.json: recorded status pass and 288 checked states. No independent rerun during the timing quiet period.
- Parent reports 16 functional checks, bare offset-zero comparison, and 19 Python QA checks passed. Those checks were not rerun or independently reinterpreted in this addendum.
- Numerical equivalence and benchmark results remain execution evidence owned by the main validation task.
