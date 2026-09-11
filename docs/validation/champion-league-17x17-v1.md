# 17×17 champion league result

The formal league completed on 2026-09-11 from Git commit
`e9edffc0a0cdffaa75d9e3d4a9bb1e57459dfb5c`, configuration SHA-256
`9b727f9bb1f4221900b9739e4345321341182798665687981475c75b11c426a3`, and
the three independently trained final checkpoints recorded in the committed
configuration. It used an NVIDIA GeForce RTX 4060 Ti, PyTorch 2.11.0+cu128,
CUDA 12.8, and 128 PUCT simulations per move.

## Integrity

- 10,000 games, 5,000 same-seed color pairs, and 906,930 plies were read back
  from 102 JSONL/Gzip shards.
- Every game ID was unique; both legs of every pair had swapped colors, the
  same seed, and an action count equal to the recorded ply count.
- The resumable runner revalidated all recorded shard hashes and all three
  checkpoint hashes before reproducing the final result.
- Mean game length was 90.693 plies, median 69, with a range of 8–381.

## Cross-play matrix

Scores count a draw as one half-point. Intervals are 95% Wilson intervals for
the first entrant's score.

| First entrant | Second entrant | W-L-D | First score | 95% interval |
| --- | --- | ---: | ---: | ---: |
| lineage A | lineage B | 2,413-908-13 | 72.57% | 71.03%–74.06% |
| lineage A | lineage C | 1,503-1,807-24 | 45.44% | 43.76%–47.14% |
| lineage B | lineage C | 476-2,842-14 | 14.50% | 13.34%–15.73% |

The overall ranking was:

| Rank | Entrant | W-L-D | Score |
| ---: | --- | ---: | ---: |
| 1 | lineage C | 4,649-1,979-38 | 70.03% |
| 2 | lineage A | 3,916-2,715-37 | 59.01% |
| 3 | lineage B | 1,384-5,255-27 | 20.96% |

Lineage C is therefore the locked champion for the analysis-grade run. Its
checkpoint SHA-256 is
`0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`.
All three pairwise intervals exclude 50%, so this ordering is not a tie broken
only by aggregate score.

## Preliminary diversity signals

The first 16 plies used visit-distribution sampling without root noise. After
D4 canonicalization, the white first-action distributions differed materially:

| Entrant | Canonical actions | Entropy (nats) |
| --- | ---: | ---: |
| lineage A | 8 | 1.709 |
| lineage B | 12 | 2.119 |
| lineage C | 5 | 1.368 |

Pairwise Jensen–Shannon divergences were 0.211 for A/B, 0.120 for A/C, and
0.334 for B/C. Thus the independently trained models did not collapse to one
identical opening distribution. The strongest model, C, used the narrowest of
the three repertoires; strength here coincided with selective convergence, not
with uniformly greater opening variety.

White won 5,552 games, black won 4,397, and 51 were draws. The color effect was
not uniform across matchups: A/B and B/C were nearly color-balanced, while A/C
was strongly white-favored. This league balances model/color exposure but does
not isolate a rules-level first-player advantage. The next 1,000-game run uses
the same champion on both sides to remove that confounder and records full
position-level search evidence.

## Artifacts

- Matrix and provenance:
  `E:\Escape\_AI\runs\champion-league-17x17-v1\league.json`
  (SHA-256 `772eec20f54cf67a97c910fcafd00f4ccaf53825c742c93bccf15014482ae9f1`).
- Atomic game shards:
  `E:\Escape\_AI\games\champion-league-17x17-v1`.
- The final JSON contains every shard SHA-256; large game data remains outside
  Git.
