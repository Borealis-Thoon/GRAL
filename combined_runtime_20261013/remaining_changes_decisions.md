# Decisions on the remaining changes

The review used development commit `891225b2` and the relevant PR prerequisites. Four focused changes were submitted. Other candidates were checked for existing coverage, numerical behavior and measured cost before deciding whether to include them.

## Submitted separately

| Change | PR | Scope |
|---|---|---|
| Source-group bookkeeping | [#70](https://github.com/GralDispersionModel/GRAL/pull/70) | Size reader totals to the selected group count and support the existing positive byte-sized IDs, 1 to 255, in decay lookup. |
| Concentration transfer | [#71](https://github.com/GralDispersionModel/GRAL/pull/71) | Transfer independent columns in parallel for sufficiently large arrays; preserve the cast, overwrite and reset, with a serial path for small arrays. |
| Unstable vertical-velocity variance | [#72](https://github.com/GralDispersionModel/GRAL/pull/72) | Reuse the last variance while its inputs match, then evaluate the original expression when they change. |
| Worker concentration buffers | [#73](https://github.com/GralDispersionModel/GRAL/pull/73) | Offer bounded per-worker double buffers as an explicit option, off by default. |

## Already covered

| Item | Decision |
|---|---|
| Receptor candidates by grid cell | Upstream already builds a per-cell dictionary. Replacing that structure would need a separate measured benefit. |
| Reuse of particle arrays between weather situations | Current Main allocates these arrays once before the situation loop. An additional reuse guard would save no allocation in that path. |
| Local source-type lookup | The new-particle routine already stores `SourceType` locally. |
| Stack storage and repeated-height lookup | [#68](https://github.com/GralDispersionModel/GRAL/pull/68) and [#69](https://github.com/GralDispersionModel/GRAL/pull/69) cover these parts. The review assessed only the proposed additions beyond them. |

## Not included in this submission

| Candidate | Decision and reason |
|---|---|
| Search neighboring vertical layers before binary search | Rejected after 40 Main runs and component tests that include preparation. Repeated exact heights and large jumps became slower; four terrain Main cases showed no compelling overall gain. |
| Cache flow-array row references | Rejected after 30 Main runs. Component cases with cell crossings or repeated heights were about 9% to 22% slower. The best Main median improvement was 1.35%, with little benefit in the other cases. |
| Reorder wall conditions or add a global empty-wall shortcut | The small condition-order change passed 50 Main runs with identical payloads, but timing ranges overlapped and some component cases slowed down. That evidence did not justify either the reorder or an additional whole-grid scan and global state. |
| Remove zero-gradient terms | Rejected from changes intended to preserve exact bits. The compiled shortened expression produced `-0` where the original produced `+0`, even with finite guarded inputs. |
| Use output-height extrema for removal checks | Deferred. The earlier estimate combined this idea with already covered stack storage; it did not establish a separate benefit for the extra boundary and reflection logic. |
| Broader meteorology caches and local copies of particle-phase settings | Deferred. The narrow variance reuse was submitted as #72; larger caches and snapshots still need an isolated benefit and a clear account of when their values can change. |
| Batch new-particle claims or reorder residual-cell work | Deferred as separate opt-in proposals. Changed arrival order affects shared float sums and later residual split decisions. Gains on the current engine have not been isolated, and scanning or sorting can outweigh scheduling savings. |
| Delay waiting for the concentration writer | Deferred pending a separate review of output-array ownership and final-output synchronization. |

For the neighboring-layer search, component timings include profile preparation. Main timings cover the complete engine run.
