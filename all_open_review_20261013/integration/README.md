# Combined PR regression checks

This package combines GRAL #62, #63, #64 and #66 through #75 on V2701 commit `891225b2f9dbbcda7f5ef6e9ef6db65e64845108`. The before variant contains the PR heads at the start of the review. The after variant adds the one-particle-floor exit in #63.

Both variants built with warnings treated as errors and completed 30 Main runs across six synthetic conditions. Five single-worker conditions produced identical concentration payloads before and after the change and across repeats. These include 108 selected groups with an extra, unused group 255 in the emissions header.

The four-worker unstable mixed-source condition was repeated five times per variant with worker buffers enabled. Its largest between-build relative L1 difference was 2.824e-9, equal to the largest within-build repeat difference, with at most five of 4,000 cells differing. Every decoded concentration was finite and nonnegative. The remaining float residual accumulation retains parallel addition-order variation.

An initial trial required byte equality in that parallel condition and stopped after 18 successful engine executions when two cells differed (relative L1 1.177e-9). The final suite above compares five repeats per build to distinguish that existing variation from a regression. Execution times are recorded for traceability; this suite is a correctness check.

## Reproduce

Use Python 3, Git and .NET 10. Pass a local GRAL Git checkout containing the base commit and a new scratch directory:

```
python reproduce.py --repo /path/to/GRAL --work /path/to/new-scratch
```

The script reconstructs both source variants from the base commit and the included patches, verifies source hashes, builds them, and runs the supplied inputs. `validation.json` contains the recorded results; a rerun writes fresh results under the scratch directory.
