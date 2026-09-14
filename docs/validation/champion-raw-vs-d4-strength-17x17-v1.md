# 17×17 raw versus D4 evaluator strength result

## Result

The direct matched-color experiment completed 2,000 games and classifies the
role-aware D4 ensemble as **superior** to raw inference from the same lineage-C
checkpoint. D4 won 1,436 games, lost 523, and drew 41, for a score of
**72.825%**. The pre-registered seed-cluster 95% interval is
**71.047%–74.603%**, wholly above 50%.

The effect survives both color assignments. D4 scored 85.70% as White and
59.95% as Black; raw scored 40.05% as White and 14.30% as Black. In particular,
D4 as the second player defeated raw White in 586 games and lost 387, so the
known first-player advantage cannot explain the aggregate result.

This answers the ablation left open by the symmetry audit. Averaging the eight
role-aware views does not dilute the checkpoint's useful policy. It removes a
large coordinate-frame defect and produces a substantially stronger agent,
without changing the network weights, rules, or PUCT budget.

## Provenance and integrity

- Generation and analysis Git commit:
  `f69a5d0c6c731a8a95ca484402ab4adb7da5d4e6`.
- Configuration:
  `configs/games/champion-raw-vs-d4-strength-17x17-v1.yaml`, SHA-256
  `5da2870caf9a2fecc5426f27dbb2eb141c5b896f42c72e5b7d45c1ea1261969c`.
- Checkpoint: lineage C generation 199, SHA-256
  `0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`.
- Independent seeds: exactly `20262912` through `20263911`; every adjacent
  pair shares one seed and reverses the raw/D4 color assignment.
- Search: 512 PUCT simulations, `c_puct=1.5`, 16 parallel leaves,
  temperature 0.8 through ply 19 and zero thereafter, no root noise, 16 stored
  candidates, and reply-resistance features enabled.
- Hardware: NVIDIA GeForce RTX 4060 Ti, 28 logical CPUs, PyTorch
  2.11.0+cu128, and CUDA 12.8 on Windows 11.
- Manifest:
  `E:\Escape\_AI\runs\champion-raw-vs-d4-strength-17x17-v1\progress.json`,
  SHA-256
  `b921354d76841a85ccbb6c5a1917f2c4bc7b21d44f284532ae45af25c28cfaf8`.
- Analysis:
  `E:\Escape\_AI\runs\champion-raw-vs-d4-strength-17x17-v1\analysis.json`,
  SHA-256
  `44cda3bf0fb86df61f4d38e0ef865f4a2401b6887e529a5022cd42e97a4d2508`.

The data comprise 50 atomic Parquet shards, 2,000 unique games, 1,000 unique
seeds, 125,761 move rows, and 29,435,496 compressed bytes under
`E:\Escape\_AI\games\champion-raw-vs-d4-strength-17x17-v1`. Every recorded
path, byte count, and shard SHA-256 matched. Every shard embedded the expected
schema, run ID, tier, generation commit, configuration hash, checkpoint hashes,
evaluator settings, and White-first mode.

DuckDB found no missing or duplicate ply, inconsistent per-game metadata,
seed/index mismatch, or evaluator-assignment error. Every seed had exactly two
games: raw White versus D4 Black at the even index, then D4 White versus raw
Black at the odd index. All rows used schema 1, board size 17, and 512 search
simulations. The built-in match analyzer independently accepted all 1,000
pairs.

Generation ran from 2026-09-13 06:01:30 through 2026-09-14 12:01:30 China
Standard Time. The measured generation time was 107,995.30 seconds, or
29 hours 59 minutes 55 seconds; atomic analysis completed three seconds later.

## Paired inference

The two-game seed cluster is the pre-registered independent sampling unit.
D4's score within each pair had this distribution:

| D4 pair score | Seed pairs |
| ---: | ---: |
| 0.00 | 39 |
| 0.25 | 13 |
| 0.50 | 432 |
| 0.75 | 28 |
| 1.00 | 488 |

D4 won 516 seed pairs, raw won 52, and 432 tied. The exact two-sided sign-test
value over the 568 non-tied pairs is `p = 4.32e-97`. The clustered mean is
72.825%, with a normal 95% interval of 71.047%–74.603%. Since its lower bound
is above 50%, the result meets the pre-registered `d4-superior` criterion by a
wide margin; the five-point non-inferiority fallback is not needed.

Individual games give the same descriptive conclusion: D4's decisive win rate
was 73.303%, with Wilson 95% interval 71.300%–75.215%. This interval is not the
primary inference because games sharing a seed are intentionally coupled.

## Color and initiative

| Evaluator and color | Wins | Losses | Draws | Score |
| --- | ---: | ---: | ---: | ---: |
| D4 White | 850 | 136 | 14 | 85.70% |
| D4 Black | 586 | 387 | 27 | 59.95% |
| Raw White | 387 | 586 | 27 | 40.05% |
| Raw Black | 136 | 850 | 14 | 14.30% |

The 25.75-point gap between each evaluator's White and Black scores is
consistent with the separately measured initiative effect, while the
45.65-point gap between evaluators within either color isolates D4's strength
advantage in this balanced schedule. These are match-specific descriptive
contrasts, not an additive game-theoretic decomposition.

The common seed controls the opening random-number stream, but it does not make
paired trajectories identical: raw and D4 can assign different probabilities
to the same draw and immediately diverge. The result estimates their expected
strength under the same stochastic continuation protocol.

## Game shape

D4's 1,436 wins comprised 1,298 escapes and 138 traps. Raw's 523 wins comprised
447 escapes and 76 traps. The 41 draws all exhausted legal moves and averaged
355.81 plies.

Across all games, length averaged 62.88 plies, with median 37.5 and range
7–372. D4 wins averaged about 52 plies, whereas raw wins averaged 69.66 plies
when escape and trap outcomes are pooled. Raw therefore tended to require
longer reversals to overcome the stronger evaluator. The long draw tail also
explains why the mean is much higher than the median.

## Interpretation and next experiment

The original lineage-C training did not fail. Its weights contain useful
structures that become much stronger when evaluated consistently across the
game's role-aware D4 orbit. The failure was narrower: raw inference attached
too much meaning to absolute board orientation. Keeping the original raw
checkpoint and games as a baseline remains scientifically useful.

The ensemble pays for eight transformed network views. The next lineage should
train role-aware D4 augmentation natively, so a single network evaluation can
approach the ensemble's consistency and strength. Two preregistered branches
are needed: symmetry fine-tuning from lineage C to test efficient repair, and a
fresh symmetry-native lineage to test whether the inherited coordinate bias
limits the repair. Their fixed-budget league must include raw lineage C, the D4
ensemble, and reciprocal-color cross-play. Symmetry audits remain a separate
gate: strength alone cannot prove equivariance.
