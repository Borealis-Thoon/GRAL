For double-precision accumulation, I would keep arrays for ordinary cases and offer your dictionary approach as an option for large, sparse outputs where the full concentration array takes substantial memory.

I tested your `ConcurrentDictionary` branch with two small changes. Grouping occupied cells by output height and source group once per output call avoids scanning the full dictionary for every group/height file. Static `AddOrUpdate` callbacks avoid captured delegates and reduce temporary allocations.

Whole-process medians from three measured runs after a warm-up:

| Case | Double array | Corrected dictionary | Dictionary with both changes |
|---|---:|---:|---:|
| 240 × 240 cells, 99 groups, 9 heights, 4 workers | 10.61 s / 766 MiB | 14.43 s / 172 MiB | 7.82 s / 170 MiB |
| Same grid and groups, 1 height, 4 workers | 3.77 s / 172 MiB | 4.06 s / 138 MiB | 4.11 s / 105 MiB |
| 60 × 60 cells, 26 groups, 1 height, 14 workers | 2.16 s / 51 MiB | 3.53 s / 84 MiB | 3.55 s / 50 MiB |

Memory is peak process commit. These cases use 1,000 particles/s on a Ryzen 9 9950X3D. In the first case, the dictionary with both changes used about 26% less time and 78% less memory than the double array. Grouping accounted for the time saving. Static callbacks reduced the 26-group dictionary's peak commit from 84 to 50 MiB, with little change in runtime. The remaining slowdown with many workers makes me favour a selectable path over replacing arrays everywhere.

![Dictionary output grouping: time and memory by workload](https://raw.githubusercontent.com/Borealis-Thoon/GRAL/evidence/dictionary-review-20261014/followup/figures/dictionary_followup_tradeoff.png)

Before comparing, I made small corrections to preserve residual contributions and restore the centre-cell condition in odour output and the receptor null check. Across 148 additional model runs, all measured steady-state comparisons and the one-worker transient comparisons matched the double array exactly. Four-worker transient differences were tiny (maximum relative L1 of 6.0e-10 for the combined variant). Each build also matched 980 writer outputs covering odour, deposition, ASCII and compressed formats, including consecutive output calls.

Raising the group limit also needs changes outside the dictionary: a 102-group input still stops in the existing source-group arrays. I would handle that separately from the storage choice.

Would you prefer an optional sparse path alongside the array, or further work toward a single dictionary backend? I favour the first option based on these results and will follow whichever direction you prefer. The [test inputs, results and small patches](https://github.com/Borealis-Thoon/GRAL/tree/evidence/dictionary-review-20261014) are available for review.
