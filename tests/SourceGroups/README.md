# Extended source groups

The calculation core accepts unique positive Int32 source group IDs and maps them to compact internal indices. Arrays for emission totals and decay rates use the selected group count, so sparse IDs do not allocate memory up to the largest ID. Particle and source IDs use `int` instead of `byte`.

The [companion GUI extension](https://github.com/Borealis-Thoon/GUI/tree/codex/extend-gui-source-groups) removes the GUI's 99-group limits in editing, input generation, and result analysis. Its regression suite includes GUI-generated inputs, this core, and GUI result evaluation for 302 groups. Both contributions are needed for that workflow. Unmodified GUIs retain the restriction; do not save extended projects through the stock GUI.

## Tests

Requirements: .NET 10 SDK. The simulation comparison also uses Python 3 and its standard library.

From the repository root:

```powershell
dotnet build src/GRAL.csproj -c Release -o artifacts/source-groups/core
dotnet run --project tests/SourceGroups/SourceGroups.csproj -c Release -- artifacts/source-groups/components
```

The component harness tests configuration validation, compact indexing, all four source readers, decay mapping, temporal headers, concentration/deposition output, and odour filenames. The odour fixture checks names only.

Build an unmodified checkout of the same base commit into a separate directory. Then compare both engines, replacing the baseline DLL path below with that build:

```powershell
py -3 tests/SourceGroups/validation.py --original "D:/GRAL-baseline/bin/GRAL.dll" --patched "artifacts/source-groups/core/GRAL.dll" --output "artifacts/source-groups/simulations"
```

The simulation output directory must be new. The test creates all meteorology and emissions; it does not require research data. On other platforms, use the installed Python 3 command instead of `py -3`.

The comparison covers 99 groups with byte-identical concentration payloads, 100/300 groups, sparse IDs through 2147483647, invalid configurations, and 101 distinct groups over 101 hourly steps. The original engine can accept a 100-group fixture even though the GUI stops at 99; its other storage/parsing limits remain visible with 300 groups and high IDs.

## Limits and restart contract

This is functional validation on a small flat domain. It does not establish production-domain accuracy, long-run convergence, or practical capacity for thousands of groups. Memory and particle requirements still grow with the selected group count.

The existing checkpoint format stores group counts, not external IDs or their order. Restart only with the identical group list and ordering and unchanged model inputs. Use a fresh computation directory if these change. This core change does not add checkpoint fingerprints; the separate research launcher is not part of this contribution.

Missing selected columns retain the existing default emission factor of 1. Unselected temporal columns are ignored. Selected factors must be finite and nonnegative, and duplicate temporal headers are rejected.
