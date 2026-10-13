# Emission columns for unselected source groups

`emissions_timeseries.txt` can contain more source groups than the current project selects. The reader maps each header ID to an internal group index, but its fallback writes to that index even when the lookup returns -1. The resulting array exception stops reading the file. The exception is printed and caught, so the simulation can continue with a partly filled factor table and zeros in later rows.

The patch skips unselected columns before indexing. It also sizes the mean-factor array by the number of header columns, matching the existing column index, and omits skipped groups from the mean-factor log. The change is one source file, three added lines and one removed line, or 322 added-plus-removed characters including indentation and excluding line endings.

For a project selecting group 1, a header of `date;hour;2;1` previously produced factors `[1, 0, 0]` instead of the supplied `[0.5, 2, 1]`. The patched reader reads all three rows and reports the selected group's mean factor as 1.17. Groups absent from the header and missing selected values keep the existing default factor of 1.

## Results

- Four strict Release builds passed with zero warnings and errors.
- The actual reader method was compiled with a small state fixture and checked against explicit factor tables in 13 cases per build, with 160 assertions in total. Cases include reordered headers, extra columns in different positions, an absent selected group, missing row values, ignored text in unselected columns and the existing duplicate-header behavior.
- The full engine ran eight synthetic conditions twice in four configurations: baseline and candidate, each with the supplied header and its equivalent header containing only selected groups. All 64 executions completed. Ten baseline runs reproduced the caught reader exception and changed concentration payloads.
- All 32 candidate executions matched the corresponding baseline run with the equivalent selected-only header. The comparison covered 192 concentration payload pairs. Every repeated execution retained identical payloads.
- The Main cases used a 200 m square domain, 10/20/40 m grids, 100/1,000/3,000 allocated particles, point, area and mixed source types, three transient situations and one worker.

`results/figure_data.json` and `results/figure_data.csv` contain the single-group example. `results/main.json` records every Main run and payload hash; `results/baseline_reader.json` and `results/candidate_reader.json` contain the factor tables and mean-factor logs. Build logs use `WORKSPACE` in place of the local working directory.

## Reproduce

Requirements: .NET 10 SDK, Git and Python 3. The Python scripts use the standard library only. Run the commands from this evidence folder and choose unused output directories.

```sh
git clone https://github.com/GralDispersionModel/GRAL.git baseline
git -C baseline checkout 891225b2f9dbbcda7f5ef6e9ef6db65e64845108
git clone baseline candidate
git -C candidate apply ../source.patch
python verify.py --baseline-source baseline/src --candidate-source candidate/src --out validation
```

Use `--dotnet /path/to/dotnet` when the SDK is not on PATH. Each engine run has a 60-second limit; the suite stops before scheduling another run after 840 seconds. Build steps also have individual time limits. The inputs are generated from the included synthetic template and case definitions.

`source_manifest.json` records every top-level source file in both tested builds after removing a UTF-8 BOM and normalizing CRLF to LF. The only source difference is `ReadEmissionTimeSeries.cs`.

[Before and after figure](figures/emission_columns.png) and [editable SVG](figures/emission_columns.svg). Run `python render_figure.py` to redraw the figure from `figure_data.json`.
