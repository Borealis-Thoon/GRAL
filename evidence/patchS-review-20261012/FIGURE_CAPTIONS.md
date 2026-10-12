Source lookup keeps the first cumulative match

Zero counts create repeated prefixes in this lookup test. The binary search selects the same first matching source as the linear scan.

Source lookup: fewer comparisons, measured batch times

For the synthetic source list, binary search uses fewer particle-to-prefix comparisons. The timed batches include prefix construction. On this host it is slower with 16 sources and faster with 256 or 4,096 sources. These timings cover the lookup helper; they do not measure the full GRAL calculation.
