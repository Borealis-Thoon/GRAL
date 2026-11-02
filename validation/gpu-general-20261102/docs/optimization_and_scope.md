## Optional GPU execution and CPU fallback

This change adds optional GPU execution for transient LINE and AREA sources. CPU execution remains the default. With `INU_GPU_EXPERIMENTAL=1`, the host checks each situation before dispatch and sends eligible residual and fresh particles to the GPU. A valid configuration outside the supported GPU subset uses the existing CPU drivers and prints `GPU fallback to CPU: <reason>`.

The current GPU subset requires terrain mode, `IStatistics=4`, a fixed random seed, 1 to 9 concentration slices, and 0 to 50 receptors away from buildings. It accepts LINE sources, AREA sources, or both, with zero decay and no deposition. Point sources, tunnel portals, buildings, wet deposition, odour, vertical concentration output, tunnel options, adaptive roughness, and nonzero log level use CPU execution. Steady-state calculations and calculations without terrain also use CPU execution. Invalid arrays or particle ranges remain errors.

GPU configuration support and GPU runtime health are separate checks. Missing Python or NVRTC settings, CUDA failures, nonfinite device trajectories, malformed frames, and result validation failures abort the run. They do not trigger a CPU restart after partial GPU work. CPU fallback for an unsupported configuration occurs before that situation executes on the GPU.

Extending the earlier AREA-only subset to LINE plus AREA dispatch changes three existing production files: `Program.cs`, `GpuExperimental.cs`, and `GpuSituationDriver.cs`. The generated CUDA already processes the common trajectory path for LINE and AREA particles. The host calculates initial coordinates before transferring them. The underlying GPU proposal also includes the runtime and source allocation changes shared with CPU execution.

## What reduces GPU overhead

Each particle still follows the generated trajectory calculation. Most supporting changes avoid repeated process startup, compilation, allocation, transfer, or host-side copying.

| Change | Mechanism and expected advantage | Code and available measurements |
|---|---|---|
| Persistent Python process and CUDA context | One server handles successive situations. Its context and loaded CUDA module survive until the host closes the connection, avoiding their recreation for every situation. | `GpuExperimental.cs`, `GpuServerConnection.cs`, `server.py`: `context_ms`, `module_load_ms`, `init_count`. |
| Optional PTX cache | A local disk cache reuses compiled PTX. Its key includes CUDA source, field manifest, Python state layout, compilation options, NVRTC version, and compiler DLL hashes. Size, schema, key, and PTX integrity checks reject invalid entries. The runtime compiles again when an entry cannot be used. | `ptx_cache.py`, `server.py`: `cache_status`, `cache_read_ms`, `cache_write_status`, `nvrtc_compile_ms`, `post_load_abi_ms`. |
| Resident device buffers | The server reuses named device allocations when their capacity is sufficient. A larger request replaces only the allocation that needs more capacity. This reduces repeated allocation and free operations. | `server.py`: `buffer_allocation_count`, `buffer_reuse_count`, `buffer_free_count`, `device_buffer_bytes`, `peak_device_buffer_bytes`. |
| Static-input fingerprint cache | The host hashes selected particle metadata and geometry spacing fields. It omits unchanged fields only after the server acknowledges their previous transfer. The host also sends receptor CSR arrays once per server. Changing meteorology and other uncached fields still transfer. | `GpuInputCache.cs`, `GpuSituationDriver.cs`: `cache_hash_s`, `omitted_field_names`, `saved_payload_bytes`, `saved_receptor_payload_bytes`, `bytes_sent`, `h2d_bytes`. |
| No repeated fresh-input transfer at execution | The situation initialization supplies fresh-particle arrays. The fresh execution request contains the phase and range without another array payload. Residual requests still supply their batch arrays. | `GpuSituationDriver.cs`, `server.py`: `bytes_sent`, `h2d_bytes`, `fresh_roundtrip_s`, `residual_roundtrip_s`. |
| Small status read after each launch | Each kernel launch returns only the device error fields. A full state read at the end of each execution request preserves scalar changes before the next state bind. | `server.py`: `status_d2h_bytes`, `status_d2h_ms`, `state_d2h_bytes`, `state_d2h_ms`, `kernel_launches`. |
| Buffered host transport | The C# connection uses 1 MiB buffers for both input and output. The receive buffer reduces small reads from the Python stdout pipe. | `GpuServerConnection.cs`: `bytes_received`, `result_request_to_header_s`, `result_transfer_apply_s`. |
| Span access and direct result application | Primitive host arrays expose byte spans for transfer. Results stream into the existing host arrays, avoiding an additional full result-array copy on these paths. A scratch-buffer path covers other layouts. | `GpuFieldExport.cs`, `GpuFieldImport.cs`: `result_transfer_apply_s`. |
| Chunked padding checks | The importer checks missing jagged cells and trailing array padding in chunks. Nonzero padding still causes an error. The check accepts floating-point positive and negative zero. | `GpuFieldImport.cs`: `ReadZeros`, with transport and result-application time available from the situation metrics. |

`TieredCompilation=true` remains unchanged in `GRAL.csproj`. It is not a new optimization in this change.

Both execution modes share `ParticleManagement.Calculate(true)` for transient situations. It allocates particles to sources with positive applicable emissions and, where the time-series bounds apply, a positive hourly factor. The particle arrays retain their allocation when capacity is sufficient. This shared host work belongs in the CPU baseline as well as the GPU path.

These mechanisms identify work that the implementation avoids. The combined CPU/GPU comparison cannot assign a measured speedup to each optimization without separate ablation runs. CUDA events supply `kernel_device_ms` for device execution. The host fields `fresh_kernel_ms`, `residual_kernel_ms`, and `kernel_total_ms` include the server launch wrapper, synchronization, and status read. Host round-trip and result-application times cover different work and must remain distinct from whole-process time. Several server metrics are cumulative, so interval analysis must use differences between records.

## Review and interface question

Would a separate GRAL GUI PR be useful for CPU/GPU selection, a visible CPU fallback reason, and Python/NVRTC checks before launch? The engine currently reads environment variables, and CPU remains the default.
