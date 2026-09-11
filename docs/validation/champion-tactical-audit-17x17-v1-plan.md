# 17×17 champion tactical-audit protocol

The champion analysis identified two concrete positions where 512-simulation
PUCT may be unreliable. This protocol freezes those serialized states through
their source manifest and 64-bit state hashes before any deeper result is
observed.

`configs/tactics/champion-tactical-audit-17x17-v1.yaml` performs two root
audits at 512, 2,048, 8,192, and 32,768 simulations:

- game 687, ply 69: Black has 262 legal actions, but action 200 is the unique
  reply that prevents continued leftward motion and instead sends the ball
  down; the played action 23 continues left and loses two plies later;
- the opening position after actions `[206, 168]`: compare actions 132 and 116,
  whose 512-simulation ranking was opposite to their sampled continuation
  results.

The audit records target priors, visits, mean values, ranks, top-20 actions,
root values, policy entropy, and rule-derived transition effects at every
budget. It then forces actions 132 and 116 and plays 64 continuations per action
using identical seeds. Continuation play matches the original analysis policy:
512 simulations, temperature 0.8 through ply 20, deterministic thereafter,
and no root noise. Reply-resistance extraction is disabled because it does not
affect play and is unnecessary for outcome comparison.

The source manifest, all source shards, checkpoint, configuration, saved state
hashes, and clean Git commit must validate before search begins. The atomic
result is written outside Git to
`E:\Escape\_AI\runs\champion-tactical-audit-17x17-v1\result.json`. A compact
post-run interpretation and result hash will be committed after completion.

This experiment distinguishes three hypotheses:

1. deeper root search finds and promotes the one-move defense;
2. the opening branch reversal persists under matched randomness, indicating a
   value/search error rather than seed imbalance;
3. the reversal contracts under matched continuations, indicating that the
   original 3/23 versus 19/28 split was mostly sampling variance.
