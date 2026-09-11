# 17×17 champion strategy analysis

## Result

The 1,000-game analysis run completed on 2026-09-11. It provides strong
evidence that Escape has rich tactical and medium-horizon strategic variation,
but not that its strongest opening play is broadly distributed. The champion
converged heavily on one first-placement motif, then branched rapidly into
nearly unique continuations. Its games exhibited three materially different
plans: direct escape corridors, static trapping before the ball moved, and
replacement-driven redirection of an established gradient.

The same lineage-C checkpoint controlled both colors. White scored 68.40%
(680 wins, 312 losses, 8 draws); among the 992 decisive games, White won 68.55%
with a 95% Wilson interval of 65.59%–71.36%. This removes unequal model strength
as the explanation for the league's color imbalance, but it does not yet
separate a rules-level first-player advantage from learned policy or orientation
bias.

## Provenance and integrity

- Generation Git commit:
  `6b7a08af2bbb678c71e7c644a57285a56a9e5b82`.
- Configuration: `configs/games/champion-analysis-17x17-v1.yaml`, SHA-256
  `802fa6cd2f70bd86b898cf778712e738455e21cd0689fcf8f5c92e2a95f96858`.
- Seeds: 1,000 independent seeds from `20260912` through `20261911`. Because
  both colors used the same checkpoint, color swapping would be identical and
  the runner did not duplicate seeds into nominal pairs.
- Model: lineage C generation 199, SHA-256
  `0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`.
- Search: 512 PUCT simulations per move, `c_puct=1.5`, 16 parallel leaves,
  temperature 0.8 for the first 20 plies, then deterministic play; no root
  noise; 16 stored candidates; reply resistance enabled.
- Hardware: Intel Core i7-14700 (20 cores/28 threads), 32 GiB RAM, NVIDIA
  GeForce RTX 4060 Ti 8 GiB, driver 581.57. Software was PyTorch 2.11.0+cu128,
  CUDA 12.8, DuckDB 1.5.5, and PyArrow 24.0.0.
- Wall-clock generation: 8,649.77 seconds (2 h 24 min 10 s), from 11:49:34 to
  14:13:49 China Standard Time; approximately 416 games or 24,822 moves/hour.
- Data: 50 Parquet shards, 1,000 unique games, 59,632 moves, and 13,284,234
  compressed bytes under `E:\Escape\_AI\games\champion-analysis-17x17-v1`.
- Manifest: `E:\Escape\_AI\runs\champion-analysis-17x17-v1\progress.json`,
  SHA-256 `07f4351b3718becaaa2a693b4947ec91ea00d82ccec6e6d309db3254ce4d74bc`.
  It contains the path, size, move/game counts, and SHA-256 of every shard.
- Summary: `E:\Escape\_AI\runs\champion-analysis-17x17-v1\analysis.json`,
  SHA-256 `51522298c282b0ddbf8f715c1f9f0fc266dd97667b577d33b6115512a4b9f82c`.

All 50 shard sizes and hashes matched the manifest. Their embedded run ID,
tier, generation commit, configuration hash, and both checkpoint hashes also
matched. DuckDB found exactly 1,000 game IDs and 59,632 rows, with no duplicate
or missing ply in any game, no seed/index mismatch, and no per-game variation
in winner, reason, board size, search budget, or model identity. All records
used schema 1, board size 17, and 512 simulations.

The post-run validation also corrected the overview's first-ball-move statistic
from zero-based ply numbering to natural one-based move numbering. The detailed
distribution was already one-based. Research-run resume now verifies both the
recorded byte count and SHA-256 of every existing shard rather than checking
only that the path exists.

## Outcomes and game shape

| Ending | White | Black | Draw | Total |
| --- | ---: | ---: | ---: | ---: |
| Ball escaped | 611 | 293 | 0 | 904 |
| Ball trapped | 69 | 19 | 0 | 88 |
| No legal move | 0 | 0 | 8 | 8 |

Games averaged 59.63 plies with a median of 45. The 10th, 25th, 75th, 90th,
95th, and 99th percentiles were 25, 31, 71, 108, 138, and 308 plies; the range
was 9–362. The eight draws were qualitatively different endgames: they averaged
358.25 plies, 34.25 replacements, and a peak of 397.75 walls. Draws are rare,
but resource-exhaustion play forms a real long tail.

There were 9,534 ball moves. Exactly 487 games used nine ball moves, the
minimum needed to escape from the center of a 17×17 board; every one was an
escape. These are straight, monotone escape trajectories rather than wandering
routes. Across all games with ball movement, the median longest consecutive
same-direction run was nine; 838 games had a run of at least five and 527 had a
run of at least nine. Thus nearly half the sample resolved through a minimum
escape corridor, while the remainder included redirections, traps, and long
construction phases.

## Opening repertoire: convergence followed by branching

| Prefix depth | Raw distinct | D4-canonical distinct | Canonical entropy |
| ---: | ---: | ---: | ---: |
| 1 | 15 | 5 | 0.608 nats |
| 3 | 464 | 458 | 4.941 nats |
| 5 | 754 | 754 | 6.307 nats |
| 10 | 991 of 999 games | 991 | 6.895 nats |
| 20 | 968 of 968 games | 968 | 6.875 nats |

The first move was strongly concentrated. Action 206, vertex `(11, 8)`, was
played in 706 games and scored 71.46% for White. Action 116, vertex `(6, 8)`,
was a distant second at 115 games. Under D4 canonicalization, 822 games fell
into the action-116 orbit. This is selective convergence on a central vertical
scaffold, plausibly a defensive seed against Black's vertical exits as well as
a future wall anchor; the data establish the motif but not that causal
interpretation.

After only three plies there were already 458 canonical sequences, and by ten
plies 991 of the 999 surviving games were distinct. Some of this diversity is
deliberately induced by temperature 0.8 through ply 20, so prefix uniqueness
alone is not evidence for 991 equally strong plans. It does show that the search
policy retains many plausible continuations after the narrow first move. The
mean visit-policy entropy was 3.247 nats in the opening, 3.390 in the middlegame,
and 3.105 late—roughly 25.7, 29.7, and 22.3 equally weighted choices if expressed
as effective counts.

D4 counts also need care: a 90-degree rotation exchanges the players' goal
axes, so canonicalization is useful for geometric shape diversity but can hide
role-specific orientation bias. Raw and canonical statistics are therefore both
retained.

## Strategic and tactical motifs

### Gradient creation before motion

The first ball move occurred in 961 games, at mean move 33.56 and median 29;
39 games ended by trapping without the ball ever moving. At first motion the
board averaged 10.19 floating posts, 21.09 anchored posts, 16.03 walls, and
294.45 legal actions. Play is therefore usually a construction contest first:
players establish a wall graph and only then create a unique shortest-path
gradient.

The direction of that first gradient was highly predictive:

| First direction | Games | White score |
| --- | ---: | ---: |
| Horizontal (left/right) | 687 | 81.95% |
| Vertical (up/down) | 274 | 31.39% |
| No movement | 39 | 89.74% |

The no-movement group comprised 35 White traps and four Black traps. This gives
two distinct successful White plans in the sample: win the race to a horizontal
gradient, or close every escape path around the stationary ball. Black's wins
were correspondingly associated with establishing the first vertical gradient.

### Forcing corridors

Reply resistance counts how many legal replies stop the ball from continuing
in its current direction. Of 9,534 ball-moving turns, 5,987 had resistance zero
and 1,100 had resistance one. That is 74.3% of all ball moves, or 82.2% of the
8,626 nonterminal ball moves where resistance is defined. The forcing share was
highest in the opening (753 of 808 ball moves), then decreased through the
middlegame (5,478 of 7,169) and late phase (856 of 1,557). Once a gradient is
created, long nearly forced corridors are the dominant tactical mechanism.

### Replacements as nonlocal tactical resources

The games contained 3,145 replacements: mean 3.15, median two, range 0–38.
Only 219 games had none. There were 376 opening replacements across 326 games,
1,914 middlegame replacements across 681 games, and 855 late replacements
across 141 long games. Replacing a remote floating post can create multiple
walls and change global shortest-path distances, so tactical effects are not
confined to the ball's neighborhood.

Game `champion-analysis-17x17-v1-00000687` is a concrete example. On ply 68,
White placed at vertex `(11, 0)`, moving the ball left from `(10, 3)` to
`(10, 2)`. Black had 262 legal moves but exactly one reply—action 200 at
`(11, 2)`—that stopped the leftward continuation; it would instead have moved
the ball down. Black chose action 23 at `(1, 5)`. White then replaced the post
at `(1, 1)`, formed two walls, and reduced reply resistance to zero. Black's
next move could not prevent a left-edge White escape.

This example also exposes a search-horizon weakness. At Black's missed defense,
512-simulation PUCT assigned the chosen action a mean value of +0.991 and the
root +0.988 from Black's perspective, even though the unique geometric defense
was available and the game was lost two plies later. The stored values are
search estimates, not solved values; this position is a high-priority target
for deeper tactical re-search.

### A reproducible opening branch anomaly

After the shared two-ply prefix `[206, 168]`—placements at `(11, 8)` and
`(9, 6)`—the position occurred 55 times. At White's third move, PUCT gave action
132 at `(7, 6)` 235 visits and mean value +0.692, versus 163 visits and +0.236
for action 116 at `(6, 8)`. Nevertheless, sampled continuations after action
132 scored only 3/23 for White (13.0%, 95% Wilson interval 4.5%–32.1%), while
action 116 scored 19/28 (67.9%, interval 49.3%–82.1%). Continued opening
sampling is a confounder, so this is not a proof that the PUCT ordering is
wrong. The reversal is large enough to justify forced-branch rollouts and a
higher-budget root search.

## How strategically rich is Escape?

The current evidence supports a qualified **yes**:

- different games win by minimum escape, delayed redirected escape, static
  trap, or rare board-exhaustion draw;
- first-gradient direction separates competing strategic objectives cleanly;
- replacements and global shortest paths create nonlocal tactics;
- continuation trees become broad within three to five plies, and the same
  early position supports branches with sharply different empirical outcomes;
- forcing corridors coexist with difficult one-move defensive resources, so
  plans must combine construction, timing, and tactical verification.

The evidence also shows selective convergence rather than unconstrained
variety. One raw first move accounts for 70.6% of games, 48.7% of all games end
with the minimum nine ball moves, and most nonterminal ball movements are
nearly forced. Escape appears rich in how players construct and contest a
gradient, but comparatively narrow once a decisive corridor is established.

This is not yet a claim about the diversity of optimal play. The sample uses
one checkpoint, one search algorithm, opening randomness, and only 512
simulations in a branching factor near 300. The detected horizon error and the
large same-model White advantage both warn against treating model preferences
as solved game theory.

## Next experiments

The next work should be targeted rather than another undifferentiated batch:

1. Re-search the missed defense in game 687 at 512, 2,048, 8,192, and 32,768
   simulations, explicitly tracking whether action 200 enters and wins the root
   ranking.
2. Force actions 132 and 116 after prefix `[206, 168]`, run matched continuation
   seeds, and repeat the root evaluation at higher budgets. This tests whether
   the empirical reversal is sampling variance, value error, or search depth.
3. Run a symmetry-controlled same-model suite using rotated/reflected opening
   randomness. This can distinguish first-player advantage from checkpoint
   orientation bias more cleanly than independent seeds.

These experiments materially address the two largest uncertainties exposed by
the completed run: tactical horizon failures and the source of the 68.4% White
score.
