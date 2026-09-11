# 17×17 champion checkpoint symmetry-audit protocol

The fixed-role rules make ordinary geometric augmentation subtly different
from a board game whose two players share the same goal axis. Rotations by 90°
or 270° and reflections across either diagonal exchange horizontal and vertical
goals, so the equivalent Escape state also exchanges White and Black. The C++
rules core implements this role-aware D4 action directly; this audit first
checks its legal-action and transition equivariance before querying the model.

`configs/symmetry/champion-symmetry-audit-17x17-v1.yaml` deterministically
samples 128 distinct saved positions from each combination of:

- opening (`ply < 20`), middlegame (`20 <= ply < 80`), and late game
  (`ply >= 80`);
- White and Black to move.

This gives 768 source positions and 6,144 network evaluations across all eight
D4 orientations. For every non-identity orientation the audit maps the policy
back into the source action space and records value absolute error, policy L1
distance, Jensen–Shannon divergence, top-1 agreement, and top-5 overlap. Results
are summarized by transform class, exact symmetry, game phase, and player turn.

To measure amplification by search, four positions from every stratum are also
searched in all eight orientations with 512 PUCT simulations, `c_puct = 1.5`,
16 parallel leaves, no root noise, and temperature zero. The audit records the
same distribution metrics plus selected-action agreement, cross-orientation
action ranks, and root-value error.

Before observing results, “low symmetry error” is defined as satisfying all six
overall thresholds committed in the configuration: neural p95 value error at
most 0.05, neural p95 policy L1 at most 0.25, neural top-1 agreement at least
0.80, neural mean top-5 overlap at least 0.90, PUCT selected-action agreement at
least 0.60, and PUCT mean top-5 overlap at least 0.75. These thresholds are a
routing rule for the next experiment, not a claim of exact equivariance.

The source manifest, source shards, checkpoint, configuration, and clean Git
commit must validate before model evaluation begins. The atomic result belongs
outside Git at
`E:\Escape\_AI\runs\champion-symmetry-audit-17x17-v1\result.json`.

The next experiment is conditional on this result. Low neural and search error
will justify a direct Black-first diagnostic using the original 1,000 analysis
seeds. Material orientation error will instead require a symmetry-ensemble
evaluator so that the color asymmetry experiment is not confounded by the
network's coordinate preference.
