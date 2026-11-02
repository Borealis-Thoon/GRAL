What this change does: The candidate enables steady, point, portal and mixed-source GPU dispatch through the existing trajectory code. It transfers source time series as rectangular float arrays and excludes transient-only execution and outputs in steady mode.

Resolved finding:

1. [MEDIUM, resolved] Source time-series values bypassed finite validation (`src/GpuSituationDriver.cs:141`). With `IWET=1`, source index 0 and a column containing NaN or Infinity, the original candidate accepted and copied the value. The source reader accepts these floats, while export and runtime frame validation preserve them. The integrator added `float.IsFinite` checks inside the existing validation loop. The focused regression `source_series_rejects_nonfinite_values_before_device_launch` failed in `qa/source_series_finite_red.json` and passed in `qa/source_series_finite_green.json`. This reviewer inspected the correction. No additional helper or dependency was needed.

Reviewed connections:

- `Program.cs:733` calls the steady GPU path once. The transient call at line 722 runs only in transient mode. Residual enumeration requires transient mode, and the server rejects a steady residual request.
- Steady export omits `Conz5d` and `EmissionPerSG`. Runtime required fields and result selection use the same mode. Generated accesses to these outputs in fresh trajectories remain inside transient branches.
- Point plume and portal jet branches, random-number order and source-specific transient termination conditions remain intact. Point temperatures retain `+273`; portal temperatures retain their difference semantics. Static horizontal velocity still selects the point-source branch.
- Particle source indexes use the matching source count. Index 0 is valid because both CPU and generated trajectories return immediately for that inactive-source marker.
- Rectangular snapshots preserve column/time order without aliasing source arrays. Shape, index and nonfinite-value failures now occur before initialization. Out-of-range time rows retain the CPU fallback to static source parameters.
- Terrain, fixed-seed, deposition, receptor-capacity and other unrelated restrictions remain. Runtime errors propagate without CPU replay after device work.

Rounding check: On .NET 10.0.12, all 27,850,180 float values in `[0.01f, 0.1f]` gave identical results for `MathF.Round(x, 3)` and the float multiply, nearest-even round and divide sequence used by the horizontal-point helper. Evidence: `qa/csharp_probe_result.json`. This check emulated the arithmetic on the CPU; it did not execute CUDA `powf` or `nearbyintf` on the device.

Verification: The initial source matched `qa/implementation_new_modes.json`, which reports a strict .NET 10 build with zero warnings and errors. The initial host result records 57 passing tests. After the finite-value correction, `qa/source_series_finite_green_v2.json` records 58 passing host tests. The integrator traced the previous seven server-process failures to an unset `HOST_TEST_PYTHON`, then reran with the verified Python path. `git diff --check` passed. This reviewer avoided rebuilding the model during the integrator's observer build. The format check failed before analysis because the build host could not connect to its named pipe (`UnauthorizedAccessException`); see `qa/csharp_format_review.log`.

Verdict: Approve the reviewed source correction. No unresolved CRITICAL, HIGH or MEDIUM source defect was established. Final acceptance still depends on integration tests and full output comparisons. Device execution and scientific validation are outside this independent source review.


Final receipt: The integrator shortened the unsupported-configuration message from the source-specific wording to `zero-decay emissions without deposition required`. Reversing that single literal replacement reproduces the previous reviewed SHA256 exactly. Conditions and numeric code are unchanged. The receipt now binds to `e81aff1cd7cee1c5295c04d2bb53050f2b41aaf9c652d3f2c3dda234d35470fd`. Both `qa/overlay_v2_build.log` and `qa/bare_v2_build.log` record zero warnings and zero errors.

