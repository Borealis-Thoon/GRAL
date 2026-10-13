# Independent review of vertical-index reuse

The repeated-height lookup avoids about half the searches in earlier instrumented terrain examples. This follow-up measures the whole engine with #69 alone and tests a one-line alternative that compares height before checking the previous index and finiteness.

The baseline is V2701 `891225b2f9dbbcda7f5ef6e9ef6db65e64845108`. The current variant applies the functional #69 diff to that baseline. The alternative changes only the order of the cache-hit conditions. None of the other open PRs is included.

## Results

All three strict Release builds had zero warnings or errors. All 36 engine executions produced matching concentration payloads within each case. Six executions were warmups, leaving five interleaved timed repeats for each of the three variants in each case. Both synthetic terrain cases used 100,000 requested particles, 26 sources/groups, a 1,200 m domain, 20 m flow and concentration grids and one worker.

| Case | Original search | Current #69 | Height-first trial |
| --- | ---: | ---: | ---: |
| Area sources, 0.5 m/s, stability class 6, one slice | 4.474 s | 4.534 s (+1.34%) | 4.518 s (+0.99%) |
| Hot point sources, 2.5 m/s, stability class 2, nine slices | 2.494 s | 2.547 s (+2.15%) | 2.540 s (+1.84%) |

Times are whole-process medians and include startup and output. The trial reduced the median relative to current #69 by less than 0.4% in both cases and remained slower than the original search. It was not adopted. The timing CSV contains all individual measurements and marks warmups. `vertical_review.json` also records process CPU time, sampled memory and output-manifest hashes.

The figure pairs the new timings with the earlier 444,724 reused indices out of 889,446 instrumented requests. Those counts come from the already published [lookup evidence](https://github.com/Borealis-Thoon/GRAL/blob/442b383534f477dd78ca5e6ba5114329632a82e4/review_evidence/qa/opt1_actual_cache_hits.json).

## Reproduce

Use Windows, Python 3 with NumPy, .NET 10 and a GRAL clone containing the baseline commit. Run from this evidence folder. Use a new empty work path:

```text
python prepare.py --repo <GRAL-clone> --work-dir <new-work-dir>
python run_vertical_review.py --work-dir <new-work-dir> --qa-dir <result-dir> --dotnet <dotnet-executable>
```

The runner includes per-process and suite watchdogs. It compares every concentration payload, verifies the prescribed terrain path and checks clean completion. The package contains synthetic input templates, the two source patches, reproduction scripts, measurement records and the figure. Model outputs and executables are excluded.
