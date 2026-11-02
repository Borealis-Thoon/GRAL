# C# dispatch review

Scope: uncommitted changes in src/GpuExperimental.cs, src/GpuSituationDriver.cs, and src/Program.cs against HEAD 7bec. Review covers correctness, type safety, error handling, security, performance, completeness, and maintainability. No production code edits or model execution.

Decision: Approve this dispatch change. No actionable CRITICAL, HIGH, or MEDIUM defect found in the reviewed delta. This decision does not establish numerical equivalence of line-source CPU and GPU model runs.

Evidence:
- Program.cs:683-695 prepares the current particle allocation and coordinates before the dispatch query. Selection itself does not modify particles, concentration arrays, or GPU server state.
- Program.cs:695,722-733 uses one situation-level decision. An unsupported transient configuration executes the original residual CPU loop followed by the original fresh CPU loop. Steady mode executes its original fresh CPU loop. GPU-disabled operation short-circuits the query.
- Program.cs:700-721 still updates wet-deposition state, transient threshold, and dispersion time before execution. The guard rejects wet deposition, and does not depend on the later threshold assignment.
- GpuSituationDriver.cs:44-80 rejects point/portal sources, unsupported physics and capacities, decay, and source/particle deposition. Source-level deposition checks also cover situations with zero fresh particles and existing residual concentration. Malformed arrays/ranges and cancellation remain errors.
- Anfangko.cs:326 onward assigns line source identity, source group, mass, mode, and coordinates on the CPU. The existing fresh GPU kernel consumes those prepared particle arrays. SourceType line and area both use the existing non-point/non-portal trajectory branches, including the SourceType > 1 terrain branch. This is a static reachability assessment, not a numerical comparison.
- GpuSituationDriver.RunSituation processes residuals then fresh particles, applies the result, and returns before common transient transfer/output processing. No fallback is attempted after partial GPU work or an execution error.
- GpuInputCache refreshes noncacheable field arrays on each GPU init and hashes mutable cacheable particle arrays. A CPU-selected situation does not itself mutate the GPU cache. Reentry therefore does not reuse stale concentration output arrays.
- GpuExperimental.CanRun only changes the diagnostic reason cache. All calls are on the main situation thread. Existing execution/cleanup errors remain propagated.

Validation:
- dotnet build src/GRAL.csproj -c Release --artifacts-path ../qa/csharp_review_artifacts -v quiet: PASS, 0 warnings, 0 errors. Log: csharp_review_build.txt. Initial --no-restore attempt failed because the new isolated artifacts directory had no assets file; normal build restored it and passed.
- dotnet format src/GRAL.csproj --verify-no-changes --no-restore --include src/GpuExperimental.cs src/GpuSituationDriver.cs src/Program.cs --verbosity quiet: UNAVAILABLE. The Roslyn build host exited before formatting because named-pipe connection raised UnauthorizedAccessException. Log: csharp_review_format.txt. This is not a format pass or a source diagnostic.
- Read the external dispatch tests and dispatch_green.txt, plus dispatch_host_tests.json (recorded 56 passed, 0 failed). These are existing job evidence, not tests rerun by this reviewer. Dispatch tests exercise mixed line/area acceptance, source-level deposition with zero fresh particles, unsupported source/physics fallback, malformed-array/range errors, and cancellation. Program.cs source-string assertions are not end-to-end CPU fallback execution evidence.

Remaining evidence boundary: No GPU/device/model run was performed. Pure-line numerical parity, mixed-source numerical parity, and full-run fallback equivalence require their own execution evidence. Existing CPU driver exception-swallowing behavior is unchanged by this delta and is outside this review scope.
