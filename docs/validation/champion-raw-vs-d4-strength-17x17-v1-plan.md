# 17×17 raw versus D4 evaluator strength protocol

The raw lineage-C checkpoint is strongly orientation-sensitive, while averaging
its eight role-aware D4 views is exactly equivariant.  Symmetry correctness does
not imply playing strength: averaging contradictory views could improve useful
generalization or dilute a sharp policy.  This protocol freezes a direct
head-to-head test before observing its outcomes.

`configs/games/champion-raw-vs-d4-strength-17x17-v1.yaml` generates 2,000
official White-first games arranged as 1,000 adjacent seed pairs.  Seeds are
exactly `20262912` through `20263911`.  In the even game, raw is White and D4 is
Black; in the odd game, D4 is White and raw is Black.  The pair shares its
opening random seed, so each evaluator occupies the first-player role exactly
once and the known move-order advantage cannot determine aggregate evaluator
score.

Both agents use the identical lineage-C generation-199 checkpoint, SHA-256
`0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`.
Only the evaluator differs.  Every move uses 512 PUCT simulations,
`c_puct=1.5`, 16 parallel leaves, temperature 0.8 through ply 19 and zero
thereafter, no root noise, 16 stored candidates, and reply-resistance features.

Forty games form an atomic Parquet shard under
`E:\Escape\_AI\games\champion-raw-vs-d4-strength-17x17-v1`.  The resumable
manifest and final analysis belong under the matching directory in
`E:\Escape\_AI\runs`.  Resume requires the same clean Git commit, configuration
hash, checkpoint hash, and all recorded shard sizes and hashes.

The primary sampling unit is the two-game seed cluster.  For each seed,
`analyze-evaluator-match` computes D4's combined score divided by two.  The
primary estimate is the mean of 1,000 cluster scores with a normal 95%
confidence interval over clusters.  A paired sign test over clusters won by D4
or raw is secondary.  Individual-game decisive win rate and color-specific
scores are descriptive because the two games sharing a seed are not treated as
independent observations.

The pre-registered interpretation uses a five-point non-inferiority margin:

- if the clustered interval is wholly above 50%, D4 is superior;
- otherwise, if its lower bound is at least 45%, D4 is non-inferior;
- if its upper bound is below 45%, D4 is materially inferior;
- every other result is inconclusive.

All 1,000 pairs must contain one reciprocal color assignment, use White as the
official first player in both games, and preserve one common seed.  A malformed
pair returns the pipeline to runner debugging.  This match measures the cost or
benefit of inference-time symmetry correction; it does not replace the later
native-symmetry training experiment.
