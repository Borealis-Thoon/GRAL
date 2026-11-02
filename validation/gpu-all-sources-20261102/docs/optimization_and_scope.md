## Optional GPU execution

CPU execution remains the default. With `INU_GPU_EXPERIMENTAL=1`, the host checks each situation before dispatch. The supported GPU subset now includes POINT, PORTAL, LINE and AREA particles in transient and steady mode, including mixed-source situations. The source is pinned at `b60673164b749896c3b942d0e89753addc1c6f7b`.

GPU execution still requires terrain mode, `IStatistics=4`, a fixed random seed, 1 to 9 concentration slices, and 0 to 50 receptors away from buildings. Sources must have zero decay and no deposition. Buildings, wet deposition, odour, vertical concentration output, tunnel entrance/opposing-lane options, adaptive roughness, and nonzero log level remain outside the GPU subset. A valid unsupported configuration uses the complete CPU path and prints a fallback reason.

Invalid source arrays, particle indexes, source time-series shapes or indexes, nonfinite values, and malformed result frames remain errors. Python startup, CUDA, and device trajectory errors abort the run. The engine does not restart a partially executed GPU situation on the CPU.

## Source-specific physics and mode handling

POINT and PORTAL execution use the existing generated CUDA trajectory branches. POINT particles retain plume-rise, momentum, buoyancy, horizontal-exit classification, and source-specific lifetime behavior. PORTAL particles retain jet geometry, velocity, temperature differences, release, and lifetime behavior. Mixed POINT/AREA execution selects each particle's own source type. These paths do not substitute AREA trajectories for point plumes or portal jets.

Transient situations execute residual batches and a fresh-particle request before result import. When fresh particles are present, steady situations execute them once and perform no residual work. Steady initialization and result import omit `Conz5d` and `EmissionPerSG`, which belong to the transient path. A steady sequence represents separate meteorological situations with no continuous transient history.

The four point/portal temperature and velocity time-series tables use exact `float[,]` transport snapshots in `[column, time]` order. The host validates equal column lengths, source indexes, and finite values. It preserves the original lists and static source parameters. An index of `-1` selects the static parameter, and a time beyond the allocated table length retains the upstream static-value behavior. POINT temperature conversion and PORTAL temperature-difference semantics remain in their existing trajectory branches. The translator records the four `Arr<float,2>` transport views and reproduces the CUDA and manifest files.

Relative to the earlier LINE/AREA dispatch, this extension changes five production files with `+88/-33`: the host driver, main loop, Python server, generated CUDA, and field manifest. The complete PR contains 23 files with `+6056/-62`. Tests, the observer, translator, synthetic fixtures, and analysis remain external evidence.

## How the runtime avoids repeated work

| Mechanism | Work avoided or reduced | Available evidence |
|---|---|---|
| Persistent Python process and CUDA context | Recreating the server, context and loaded module for each situation. | Context/module timing and initialization counts. |
| Optional keyed PTX cache | Recompiling matching CUDA source. The key includes source, manifest, state layout, options, NVRTC version and compiler DLL hashes. | Cache status, compile/read/load timings and integrity checks. |
| Resident device buffers | Reallocating named buffers that already have enough capacity. | Allocation/reuse/free counters and application buffer sizes. |
| Acknowledged static-input cache | Retransferring selected unchanged metadata and grid-spacing fields. Cache state advances only after server acknowledgement. | Omitted field names, saved payload bytes, hash time and H2D bytes. |
| Fresh-input reuse | Sending fresh arrays again after situation initialization. Residual batches retain their required input transfers. | Framed byte counts and phase times. |
| Small status reads | Reading the whole state after every launch. A full state read still preserves scalar mutations at each execution-request boundary. | Separate status/state D2H bytes and time. |
| Buffered pipes | Small host pipe reads and writes. Both directions use 1 MiB buffers. | Transport contracts and result receive/apply time. |
| Spans and direct result application | Additional full-array copies on supported primitive array paths. | Wire-layout/topology tests and result receive/apply time. |
| Chunked padding checks | Scalar reads for absent jagged cells and trailing padding. Nonzero padding remains an error. | Padding contracts and result receive/apply time. |

CPU and GPU runs share active-source allocation and particle-array reuse. The CPU baseline includes those host changes. `TieredCompilation=true` remains unchanged. Combined timing comparisons cannot assign a measured speedup to one optimization without separate ablation evidence.

CUDA events supply the cumulative `kernel_device_ms` counter. Its differences give device intervals. The legacy fields `fresh_kernel_ms`, `residual_kernel_ms`, and `kernel_total_ms` include server launch, synchronization and status-read time. Device time is nested in host round trips and must not be added to them.

## What the execution evidence establishes

`phase_counts` records completed synchronized GPU execution requests on the host. It does not count source types inside the CUDA kernel. Source-specific evidence therefore combines actual single-source functional cases, fixed source-group mapping, positive concentration output in each mixed-case group, CUDA-event/launch evidence, and CPU numerical comparison. Device counters for individual source types are not measured.

The new study keeps `transient_all_sources` and `steady_all_sources` separate. Each cohort has 22 completed measured runs and four groups: SG1 AREA, SG2 horizontal LINE, SG3 POINT and SG4 PORTAL. The numerical screens pass in both cohorts. Final claims follow the independent review and remain bounded to the saved synthetic results. Prior three-group timings use a different idle protocol and remain historical evidence.
