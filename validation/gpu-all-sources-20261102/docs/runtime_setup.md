## Runtime requirements

The optional GPU runtime currently uses Windows x64 and the CUDA driver through Python `ctypes`. The reference interpreter is Python 3.12. The runtime Python files use the standard library. They do not require NumPy, CuPy, PyCUDA, or a Python CUDA package.

Build GRAL with the .NET 10 SDK because `src/GRAL.csproj` targets `net10.0`. A framework-dependent build also requires the .NET 10 runtime on the execution machine. Keep these five files together in one writable runtime directory: `server.py`, `cuda_common.py`, `ptx_cache.py`, `generated.cu`, and `fields_manifest.json`. The server writes `server_compile.log` and `state_layout.json` beside them.

GPU execution requires an NVIDIA driver that exposes `nvcuda.dll`, NVRTC 12.9, and a GPU/driver combination that accepts the compiled `compute_120` target. `cuda_common.py` loads `nvrtc64_120_0.dll` and identifies the companion `nvrtc-builtins64_129.dll`. Keep the matching NVRTC distribution together. Compilation uses `--gpu-architecture=compute_120`, `--std=c++11`, and `--fmad=false`. This implementation does not select an architecture automatically or provide a GPU device selector. It requests CUDA device ordinal 0. Other hardware targets need separate implementation and validation.

## Environment variables

Set `INU_GPU_EXPERIMENTAL=1` to request GPU execution. An unset value, `0`, or another value leaves CPU execution selected. Once an eligible GPU situation runs, `GpuExperimental.Required` requires the following five variables:

| Variable | Value |
|---|---|
| `INU_GPU_PYTHON` | Absolute path to the verified Windows x64 Python executable. |
| `INU_GPU_SERVER` | Absolute path to the working copy of `server.py`. |
| `INU_GPU_MANIFEST` | Absolute path to `fields_manifest.json` from the same runtime copy. |
| `INU_GPU_METRICS` | Writable JSONL output path. Situation records append to this file. Use a new file for each run. |
| `INU_GPU_STDERR` | New writable file path for Python stderr. The host uses `FileMode.CreateNew`, so an existing file causes an error. |

`INU_GPU_NVRTC_DIR` selects the NVRTC DLL directory. If it is unset, the runtime looks under `nvrtc/nvidia/cuda_nvrtc/bin` beside `cuda_common.py`. Set it explicitly for an NVRTC installation elsewhere.

| Optional variable | Default and accepted values |
|---|---|
| `INU_GPU_CACHE_DIR` | Unset disables the PTX disk cache. Use an absolute local drive path for an optional cache. The cache rejects UNC and remote drives. Cache lookup failures lead to compilation. |
| `INU_GPU_CACHE_COORDINATES` | Default is `0`. The host accepts only `0` and `1`. Value `1` also fingerprints `Xcoord`, `YCoord`, and `ZCoord`. Coordinates commonly change with situation-dependent seeds, so the default avoids hashing them. |
| `INU_GRAL_GPU_CHUNK` | Default `4096`, integer range `1` to `65536`. Controls particles per kernel launch. |
| `INU_GRAL_GPU_BLOCK` | Default `128`. The host accepts only `128` and `256`. |

Trace settings are diagnostic options. `INU_GPU_DEVICE_TRACE` and `INU_GPU_DEVICE_RESIDUAL_TRACE` select new output files. `INU_GPU_DEVICE_STEP_TRACE` requires `INU_GPU_DEVICE_TRACE`. `INU_GPU_TRACE_SITUATION` defaults to `1` and accepts positive integers. `INU_GPU_RESIDUAL_TRACE_COUNT` defaults to `64` and accepts `1` to `65536`. Leave trace settings unset for normal timing comparisons.

## Build and prepare an isolated run

The following PowerShell example uses placeholder paths. Replace them with paths on the target machine. Use a new run directory to keep output files and runtime diagnostics separate.

```powershell
$repoRoot = 'D:\GRAL_GPU\repo'
$runRoot = 'D:\GRAL_GPU\run_001'
$gpuPython = 'C:\Python312\python.exe'
$nvrtcDirectory = 'C:\CUDA_NVRTC_12_9\bin'
& $gpuPython --version
dotnet --list-sdks
dotnet build "$repoRoot\src\GRAL.csproj" -c Release -p:TreatWarningsAsErrors=true -o "$runRoot\build"
New-Item -ItemType Directory -Path "$runRoot\logs" -ErrorAction Stop
Copy-Item -LiteralPath "$repoRoot\gpu\runtime" -Destination "$runRoot\runtime" -Recurse -ErrorAction Stop
```

Use an existing, complete GRAL computation directory for `$computationDirectory`. Prepare a separate copy for each CPU/GPU comparison. Existing model input requirements still apply.

```powershell
$computationDirectory = 'D:\GRAL_GPU\case_001\Computation'
$env:INU_GPU_EXPERIMENTAL = '1'
$env:INU_GPU_PYTHON = $gpuPython
$env:INU_GPU_SERVER = "$runRoot\runtime\server.py"
$env:INU_GPU_MANIFEST = "$runRoot\runtime\fields_manifest.json"
$env:INU_GPU_METRICS = "$runRoot\logs\gpu_metrics.jsonl"
$env:INU_GPU_STDERR = "$runRoot\logs\gpu_server.stderr"
$env:INU_GPU_NVRTC_DIR = $nvrtcDirectory
$env:INU_GPU_CACHE_DIR = 'D:\GRAL_GPU\ptx_cache'
dotnet "$runRoot\build\GRAL.dll" $computationDirectory
```

The chunk and block defaults above apply unless those variables already exist in the process environment. The validation harness uses `INU_GRAL_GPU_CHUNK=65536` and `INU_GRAL_GPU_BLOCK=128`, so record any override when comparing timings. For CPU execution, set `INU_GPU_EXPERIMENTAL=0` in the process that launches GRAL. CPU execution does not launch Python or require the five GPU variables.

## Dispatch and failure behavior

GPU opt-in permits the engine to choose the GPU only for its supported subset. Valid configurations outside that subset use the CPU with a console fallback reason. See `optimization_and_scope.md` for the current feature boundary. This behavior preserves access to the existing CPU paths across GRAL configurations without claiming GPU coverage for every feature.

An eligible GPU situation with missing settings or a runtime error aborts. Treat Python startup failures, missing NVRTC DLLs, device errors, malformed data, and nonfinite trajectories as run failures. The engine does not silently restart that situation on the CPU. A PTX cache miss or rejected cache entry causes recompilation within the GPU path.

## Additional validation dependencies

The benchmark runner uses `psutil` for process memory and affinity capture. Its GPU telemetry uses the driver utility `nvidia-smi`. The separate analysis and plotting scripts use NumPy and Matplotlib. These dependencies belong to the validation environment and are additional to the standard-library Python server.

The benchmark observer and seed-offset overlay are separate from production source. Distinguish instrumented benchmark timing from bare-engine timing when reporting results. Runtime setup checks establish that the requested tools can load and execute. Model correctness, numerical comparisons, and scientific acceptance require their own evidence.
