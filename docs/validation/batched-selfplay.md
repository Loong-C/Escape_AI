# Batched self-play performance validation

Validated on 2026-09-04 on 17x17 with the default 450,948-parameter network,
PyTorch 2.11.0+cu128, and an NVIDIA RTX 4060 Ti.

The optimized path combines independent game roots, uses virtual loss to reserve
several leaves per root, performs legal masking and softmax over an entire tensor,
stores tree edge statistics in contiguous arrays, and skips detailed candidate
objects for training-only games.

All measurements used eight simulations per move and untrained weights. They are
throughput diagnostics, not playing-strength measurements.

| Implementation point | Concurrent games | Games/hour | Positions/second |
| --- | ---: | ---: | ---: |
| initial batched roots | 8 | 2,825 | 119 |
| initial batched roots | 32 | 3,121 | 123 |
| tensor softmax | 32 | 3,876 | 152 |
| virtual leaves + array edges | 32 | 9,121 | 380 |
| dense policy + training fast path | 32 | 15,003 | 625 |

The final measured path is about 5.3 times faster in games/hour than the first
measurement. Higher-simulation runs will not scale perfectly from these figures;
formal lineage manifests must retain their measured wall time and search budget.

The batched and scalar paths share the same visit accounting. Tests verify that
each root receives exactly the requested simulations and that every selected move
remains legal.
