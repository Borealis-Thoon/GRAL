# Review of the open GRAL pull requests

This review covers #62, #63, #64 and #66 through #75. It checks the implementation, evidence, explanations and figures against the current V2701 code and the maintainer's comments.

The source amendment is in #63: stop residual planning when every eligible entry has one particle. It changes one file, with five added and three removed lines. The other PR implementations remain as submitted.

| Evidence | What it checks |
| --- | --- |
| [Residual planning and precision](residual_precision/README.md) | Split-count preservation, 16 engine runs, planning cost, and clearer precision/memory figures |
| [Vertical search](guards_storage/README.md) | 36 engine runs comparing the original search, #69 and a condition-order alternative |
| [Transfer and worker buffers](new_optimizations/README.md) | 32 boundary/shape transfer tests, 120 #73+#74 driver checks, and the time/memory figure |
| [All-PR integration](integration/README.md) | 30 engine runs combining all 13 PRs, including 108 selected groups and repeated parallel transient tracking |

The vertical-search comparison did not establish a whole-engine speed benefit, so the experimental condition-order change was not adopted. The maintainer discussion offers a narrower change as an alternative. The transfer cutoff and optional worker-buffer budget retained their current settings after the additional checks.

Each folder contains its reproduction instructions and recorded measurements. The integration package also records the parallel repeat differences and the hashes of all reconstructed source files. Engine binaries and raw model outputs are omitted.
