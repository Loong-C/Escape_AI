# 17×17 champion tactical-audit result

## Result

The targeted audit completed on 2026-09-11 and confirmed both tactical
concerns raised by the 1,000-game champion analysis:

1. the unique defense in game 687 is a genuine search-horizon failure at the
   512-simulation analysis budget; PUCT does not visit it at all until the
   budget is increased, and it becomes the selected action only at 8,192
   simulations;
2. the outcome reversal between opening actions 132 and 116 persists under 64
   matched continuation seeds per branch. Matching reduces the original
   difference, but action 116 still outscores action 132 by 36.72 percentage
   points.

This makes the earlier finding more precise: the champion has learned useful
strategic motifs, but 512-simulation search is not deep enough to verify sparse
geometric defenses reliably in positions with roughly 300 legal actions.

## Provenance and integrity

- Audit Git commit:
  `13fe728fc74267d52aed9fbab422fec24411ace7`.
- Configuration: `configs/tactics/champion-tactical-audit-17x17-v1.yaml`,
  SHA-256
  `73c25baae8d4c2259ca6c192bd36968befd33912cde490882344e9705d74328f`.
- Root-search seed: `20260913`; matched continuation seeds: `20261912` through
  `20261975` for each forced action.
- Checkpoint: lineage C generation 199, SHA-256
  `0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`.
- Source generation commit:
  `6b7a08af2bbb678c71e7c644a57285a56a9e5b82`.
- Source manifest:
  `E:\Escape\_AI\runs\champion-analysis-17x17-v1\progress.json`, SHA-256
  `07f4351b3718becaaa2a693b4947ec91ea00d82ccec6e6d309db3254ce4d74bc`.
- Result:
  `E:\Escape\_AI\runs\champion-tactical-audit-17x17-v1\result.json`, SHA-256
  `dd4a676d293ab7129b1902de218ab435481f13f9bd703e41da1100c8314f81e5`.
- Hardware: NVIDIA GeForce RTX 4060 Ti, 28 logical CPUs, PyTorch
  2.11.0+cu128, and CUDA 12.8 on Windows 11.
- Runtime: 1,113.07 seconds (18 min 33 s), from 16:02:30 through 16:21:07
  China Standard Time.

Before search, the runner revalidated the source manifest hash, all 50 source
Parquet shard sizes and hashes, the checkpoint hash, and both serialized state
hashes. Re-running the command from the same clean commit returned the existing
atomic result and reproduced its SHA-256. The result contains all four required
budgets for both positions, 64 records for each forced branch, identical seed
ranges, and the expected rule transitions: action 200 moves the ball down,
action 23 continues left, and actions 132/116 do not move it.

## Game 687: when does search find the unique defense?

The audited position is game
`champion-analysis-17x17-v1-00000687`, ply 69, state hash
`12347505577636488699`. Black is to move with the ball at `(10, 2)` and 262
legal actions. Action 200 at vertex `(11, 2)` is the only move that breaks the
leftward continuation; action 23 at `(1, 5)` was played in the original game
and allows White's forced escape.

| Simulations | Selected | Root value | Action 200 rank/visits/Q | Action 23 rank/visits/Q |
| ---: | ---: | ---: | ---: | ---: |
| 512 | 23 | +0.988 | 150 / 0 / 0.000 | 1 / 32 / +0.991 |
| 2,048 | 185 | +0.909 | 5 / 99 / +0.999 | 21 / 53 / +0.887 |
| 8,192 | **200** | +0.267 | **1 / 416 / +0.277** | 49 / 81 / +0.235 |
| 32,768 | **200** | +0.202 | **1 / 460 / +0.157** | 213 / 89 / +0.124 |

The nominal rank 150 at 512 is only an action-ID tie break among unvisited
actions; the substantive fact is zero visits. With 262 legal actions, 512
simulations provide fewer than two simulations per legal action on average.
The network prior for action 200 was 1.78%, slightly below action 23's 2.12%,
so the correct geometric defense received no search evidence while groups of
high-prior actions consumed the budget.

At 2,048 simulations the defense is finally explored and rises to fifth, but
PUCT still chooses action 185. At 8,192 it reaches rank one and remains selected
at 32,768. At the same time the root estimate falls from +0.988 to +0.202 and
policy entropy rises from 2.773 to 5.161 nats. Deeper search discovers that the
position is far less comfortable for Black than the shallow evaluation claims,
even after it finds the correct immediate defense.

This is a branching-factor failure, not a rules error. The deterministic rules
calculation identifies action 200 directly; neural PUCT needs between 2,048 and
8,192 simulations to promote it. Tactical verification should therefore add
explicit gradient-defense candidates or selective search extensions rather
than increasing every move uniformly to 8,192 simulations.

## Opening `[206, 168]`: root search versus matched continuations

The second state is ply 2 after placements at `(11, 8)` and `(9, 6)`, state
hash `9734087719835415932`. White has not yet moved the ball.

| Simulations | Selected | Root value | Action 132 rank/visits/Q | Action 116 rank/visits/Q |
| ---: | ---: | ---: | ---: | ---: |
| 512 | **132** | +0.306 | **1 / 237 / +0.673** | 2 / 163 / +0.262 |
| 2,048 | **132** | +0.052 | **1 / 1,297 / +0.079** | 2 / 604 / +0.129 |
| 8,192 | **132** | -0.068 | **1 / 5,333 / -0.043** | 2 / 1,507 / -0.011 |
| 32,768 | **132** | -0.342 | **1 / 15,835 / -0.330** | 2 / 10,141 / -0.335 |

The visit winner never changes, but the evaluation changes radically. The root
moves from a sizeable White advantage at 512 to a sizeable White disadvantage
at 32,768. At 2,048 and 8,192 simulations, action 116 already has the better Q
despite retaining fewer accumulated visits. By 32,768 the two Q values are
nearly tied, while action 132 retains a large visit lead. Search depth therefore
corrects the position value much more strongly than it separates these two
actions.

The forced continuations used the same 64 seeds for each action, 512
simulations per subsequent move, temperature 0.8 through ply 20, deterministic
play thereafter, and no root noise.

| Forced action | White-Black-Draw | White score | Continuation plies mean/median |
| ---: | ---: | ---: | ---: |
| 132 at `(7, 6)` | 22-42-0 | 34.38% | 45.41 / 31 |
| 116 at `(6, 8)` | 45-18-1 | 71.09% | 65.70 / 39 |

Action 132's White-win 95% Wilson interval is 23.92%–46.60%. Excluding the one
draw after action 116, its decisive White-win interval is 59.30%–81.10%. The
matched-seed contingency was:

| Outcome after 132 | Outcome after 116 | Seeds |
| --- | --- | ---: |
| Black | White | 27 |
| Black | Draw | 1 |
| White | Black | 4 |
| Black | Black | 14 |
| White | White | 18 |

Action 116 improved White's result on 28 seeds, worsened it on four, and tied
on 32. An exact two-sided sign test over the 32 non-ties gives
`p = 1.93e-5`. The original unmatched sample showed 13.0% versus 67.9%, a
54.8-point difference; the matched experiment contracts that to 36.7 points
but leaves a large, statistically clear reversal. Seed imbalance contributed
noise, but it does not explain the effect.

The matched RNG streams begin after the forced action. They are common random
numbers, not identical future positions: once policies diverge, the same random
draw maps onto different visit distributions. The experiment estimates each
branch under the same continuation policy; it does not solve either branch.

## Interpretation

All three preregistered hypotheses receive a definite answer:

1. **Deeper search finds the missed defense:** confirmed. Action 200 is first
   selected at 8,192 simulations and remains first at 32,768.
2. **The opening reversal survives matched randomness:** confirmed. Action 116
   gains 36.7 score points and improves 28 paired seeds versus four regressions.
3. **The reversal contracts under matching:** also confirmed. Its magnitude
   falls from 54.8 to 36.7 points, so the original small branch samples
   exaggerated a systematic effect.

The central algorithmic lesson is that broad PUCT plus a learned prior can miss
a unique, low-prior geometric resource. More simulations eventually repair the
game-687 choice, but the opening branch remains difficult even at 32,768 root
simulations: the visit ranking and matched continuation outcomes disagree.
Potential remedies are gradient-aware candidate injection, forced-move
extensions when reply resistance is small, and training examples upweighted
from verified tactical failures.

These results strengthen the strategy-diversity conclusion. Two superficially
quiet third moves from the same opening state lead to sharply different outcome
distributions, while a single remote placement can redirect the ball and alter
the tactical status of hundreds of legal replies. The strategic tree is not
merely diverse because of random openings; local choices have reproducible,
large downstream effects.

## Next experiment

The remaining large uncertainty is the same-model White score of 68.4%. A
symmetry-controlled audit should couple opening randomness under reflections
that preserve each goal axis and under 90-degree rotations combined with color
and turn exchange. It should compare raw and transformed network evaluations,
PUCT policies, and paired outcomes. This can separate:

- rules/first-move advantage;
- checkpoint orientation bias;
- finite-search asymmetry introduced by priors or batched PUCT.

The symmetry suite should be implemented and smoke-tested first, then committed
with its formal configuration before generating any result.
