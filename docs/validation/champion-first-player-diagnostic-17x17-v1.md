# 17×17 champion first-player diagnostic result

## Result

The symmetry-controlled diagnostic completed 2,000 games: 1,000 independent
official White-first games and 1,000 role-swapped Black-first validation games.
The official arm produced 798 first-player wins, 198 second-player wins, and
four draws, for a first-player score of **80.00%**.  Among the 996 decisive
games, the first player won **80.12%**, with a 95% Wilson interval of
**77.53%–82.48%** and an exact two-sided binomial value of
`p = 6.72e-86` against 50%.

All 1,000 paired trajectories are role-swapped D4 equivalent.  The diagnostic
Black-first arm therefore reverses the colors exactly: Black won 798 games,
White won 198, and four were drawn.  For this checkpoint, D4 evaluator, search
budget, and opening policy, the large score belongs to moving first rather
than to White's horizontal goal axis.

This is an agent-level causal result, not a game-theoretic solution.  The same
imperfect policy controls both sides, opening moves are sampled, and 512 PUCT
simulations do not establish optimal play.  The result nevertheless removes
the raw checkpoint's orientation bias as an explanation for the measured
asymmetry.

## Provenance and integrity

- Generation Git commit:
  `17eaec67b0c58d0c74cc9f31cd42eab68c82a825`.
- Stabilizer-aware analysis commits: `f7a0bdc` and `2d6a506`.
- Configuration:
  `configs/games/champion-first-player-diagnostic-17x17-v1.yaml`, SHA-256
  `e91b1ceaf6eb6d785c890607017543ca8553ce21c93a87b6cd3434e19408cc38`.
- Checkpoint: lineage C generation 199, SHA-256
  `0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`.
- Independent seeds: exactly `20260912` through `20261911`; each adjacent
  White-first/Black-first pair shares one seed.
- Search: 512 PUCT simulations, `c_puct=1.5`, 16 parallel leaves,
  temperature 0.8 through ply 19 and zero thereafter, no root noise, 16 stored
  candidates, and reply-resistance features enabled.
- Evaluator: the same role-aware D4 ensemble and checkpoint for both players,
  with raw inference batches capped at 256.
- Hardware: NVIDIA GeForce RTX 4060 Ti, 28 logical CPUs, PyTorch
  2.11.0+cu128, and CUDA 12.8 on Windows 11.
- Manifest:
  `E:\Escape\_AI\runs\champion-first-player-diagnostic-17x17-v1\progress.json`,
  SHA-256
  `b6ad592f3118da4f9cbcede5a3fee64f13e8360f748252a6bb23230737a2dd20`.
- Analysis:
  `E:\Escape\_AI\runs\champion-first-player-diagnostic-17x17-v1\analysis.json`,
  SHA-256
  `678b4fca1b7cc5c5bc3396c2f54ed63a381d6b0f2fc4f311243965d60287388d`.

The data contain 100 atomic Parquet shards, 2,000 unique games, 1,000 unique
seeds, 77,736 move rows, and 14,422,090 compressed bytes.  Every manifest path,
byte count, and SHA-256 matched; there were no missing, extra, or duplicate
shards.  Every shard embedded the expected schema, run ID, tier, generation
commit, configuration hash, checkpoint hashes, evaluator settings, and paired
starting-player mode.

DuckDB found no duplicate or missing ply, no malformed game metadata, and no
seed with anything other than one White-first and one Black-first game.  All
rows used schema 1, board size 17, 512 simulations, and the expected model IDs.
The run began on 2026-09-11 at 19:25 China Standard Time.  Its first process
ended cleanly at the 1,060-game shard boundary without an application error;
the manifest and all 530 completed pairs were validated before resuming from
the same committed configuration.  Generation completed on 2026-09-13 at
05:08, after approximately 29 hours 38 minutes of active generation time.

The post-generation quality gates passed: Ruff, mypy over all 46 source files,
the PowerShell parser, and all 122 pytest tests.

## Stabilizers and exact trajectory equivalence

Of the 1,000 pairs, 999 use `rotate_270` for the entire trajectory.  Seed
`20261769` is the sole stabilizer case.  Its two games are:

- `champion-first-player-diagnostic-17x17-v1-00001714`;
- `champion-first-player-diagnostic-17x17-v1-00001715`.

They use `rotate_270` through ply three.  At ply four, the position has a
non-trivial symmetry stabilizer and the sampled actions choose two equivalent
representatives of the same action orbit.  The valid mapping then becomes
`rotate_90` for the remaining 39 plies.  Every paired pre-move state and action
still has an exact role-swapping transform, both games last 43 plies, and their
winner and reason map exactly.

The original analyzer incorrectly required one fixed transform for the entire
game.  The corrected analyzer finds a minimum-switch valid symmetry path and
records dynamic segments explicitly.  It reports one dynamic pair, one switch,
38,829 `rotate_270` paired plies, 39 `rotate_90` paired plies, and zero invalid
pairs.  A regression fixture reproduces this real six-ply prefix.  This change
relaxes only the choice of representative at a symmetric state; it still
requires an exact role-swapped state and action mapping at every ply.

## Outcomes and initiative

| Arm | First wins | Second wins | Draws | First-player score | Mean plies |
| --- | ---: | ---: | ---: | ---: | ---: |
| Official White-first | 798 | 198 | 4 | 80.00% | 38.868 |
| Diagnostic Black-first | 798 | 198 | 4 | 80.00% | 38.868 |

In the official arm, first-player wins comprised 749 escapes and 49 traps;
second-player wins comprised 156 escapes and 42 traps.  The four draws ended
because no legal moves remained.  First-player wins averaged 32.88 plies,
whereas second-player wins averaged 56.55.  The latter therefore required a
substantially longer defensive reversal rather than merely exchanging the same
short race.

Official game lengths had median 29 and range 7–364.  Their 10th, 25th, 75th,
90th, 95th, and 99th percentiles were 15, 21, 44, 63, 88.15, and 227 plies.
The long tail and the much later second-player wins support a strong initiative
effect under this policy.

## Relation to the raw 1,000-game analysis

The earlier raw-checkpoint suite used the same 1,000 seeds and gave White a
68.40% score.  Under the D4 ensemble, the official White-first score rises to
80.00%.  Across paired seeds, the D4 result improved White's outcome in 255
games, worsened it in 136, and left it unchanged in 609.

This comparison is contextual rather than a playing-strength test.  Changing
the evaluator changes both players and their continuation distributions, so a
higher self-play first-player score does not show that D4 is stronger than raw.
It does show that orientation correction did not explain away the earlier
color imbalance.  Once the goal axes are demonstrably exchangeable, the
remaining asymmetry is associated with initiative in this agent/search regime.

## Implications and next experiment

Later strategy reports must treat first- and second-player populations
separately or use paired, balanced protocols.  Opening popularity and branch
success cannot be pooled across move order as though the roles were
exchangeable.  If the same effect persists across independently trained
symmetry-aware agents, practical game balancing may eventually require a swap
rule, constrained opening protocol, or another explicit compensation; the
present experiment alone is not enough to select one.

The next formal experiment will compare the raw checkpoint evaluator directly
against its D4 ensemble.  It will share opening seeds and exchange which
evaluator occupies each fixed color, measuring evaluator strength separately
from the now-established first-player effect.  A new symmetry-aware training
lineage follows that ablation so the final agent can obtain native equivariance
without paying the eight-view inference cost.
