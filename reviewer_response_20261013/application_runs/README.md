# Application context for source groups above 99

Two applications completed on an Intel Core Ultra 7 270K Plus desktop with 32 GB RAM; the run logs recorded 31.47 GiB of visible memory. Both used 22 workers, 108 time-partitioned source groups, nine output slices and 108 weather situations.

| Grid | Interior cells | Elapsed time | Sampled working-set peak |
| --- | ---: | ---: | ---: |
| 500 m | 114 × 82 | 143.28 min | 2.17 GiB |
| 250 m | 228 × 164 | 147.76 min | 3.39 GiB |

These records show that applications with more than 99 groups can be practical on a desktop. They do not establish the memory cost or compatibility of the proposed minimal source-reader change. The historical engine included lazy group storage, other patches and a custom filename codec. It kept two-character group tokens, using `A0` through `A8` for IDs 100 through 108. The groups were time-partitioned, so all 108 were not continuously emitting together.

The audit checked every archive directory: each of the 216 archives contained exactly 972 unique slice/group members, with no missing or unexpected key. Direct decoding of the first and last situation from each run checked 3,888 members and 1,500,359 sparse values. Those samples contained no nonfinite or negative concentrations and no invalid grid indices. Groups 100 through 108 had positive outputs at the last situation in both runs. The existing full-run analyses also reported zero NaN totals; the current audit did not decode every payload again.

The memory figures are maxima of approximately two-second samples, not operating-system lifetime peaks. Nominal 32 GB is the user's hardware description; 31.47 GiB is the value in the run record. `sg_application_context.json` contains the exact measurements, audit scope and hashes of the private evidence files. Raw inputs, outputs, host identifiers and study details are excluded.
