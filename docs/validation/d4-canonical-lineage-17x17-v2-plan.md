# Canonical-D4 native lineage protocol

This protocol replaces the paused random-augmentation native lineage with a
coordinate-consistent from-scratch experiment. It preserves the network,
self-play, replay, optimizer, and 100,000-game budgets of lineage C and of the
failed V1 branch. The intended causal change is limited to symmetry handling.

## Frozen treatment

`self_play_evaluator: canonical-d4` maps each playing state to the
lexicographically smallest serialized member of its role-aware D4 orbit,
evaluates that representative once, and maps its policy back. Equivalent states
within an inference call are deduplicated. If a state is fixed by multiple D4
transforms, policy probabilities are averaged by stabilizer action orbit before
mapping back; this prevents arbitrary orientation selection on the empty board
and other symmetric positions.

`symmetry_augmentation: canonical-d4` maps every sampled replay row and its
MCTS policy into the same canonical coordinates. All source-to-canonical
mappings are averaged when the state has a stabilizer. Legal masks are
recomputed from the canonical state and values remain in the current-player
perspective.

## Runs and fixed budgets

The 3×3 mechanics gate is
`configs/lineages/canonical-d4-smoke-3x3-v1.yaml`: seed `20260920`, two
generations, eight games, 8-simulation PUCT, and five learner steps per
generation.

The formal branch is
`configs/lineages/lineage-d-d4-canonical-17x17-v2.yaml`: seed `20260921`, 200
generations × 500 games = 100,000 games, 64-simulation PUCT, 500 learner steps
per generation, a 100,000-position sample, and a 100-shard replay window. It
starts from a newly initialized network and uses the lineage C exploration
parameters.

All large outputs remain under `E:\Escape\_AI`. Both configurations require a
clean worktree and record the Git commit, configuration hash, shard hashes, and
checkpoint hashes.

## Sequential gates

1. The smoke run must complete and resume byte-stably. The complete code suite
   must pass Ruff, strict mypy, pytest, and PowerShell parsing.
2. Generation 10 is a preregistered bootstrap checkpoint. A healthy branch
   must reduce value loss below `0.90` or total loss below `6.35`; otherwise it
   is paused for diagnosis. This permissive gate is above the generation-10
   results of all three original controls and below the failed V1 plateau.
3. Generation 24 receives a frozen canonical-D4 symmetry audit and paired
   reciprocal-color match against the raw lineage C champion and its eight-view
   D4 ensemble.
4. Generations 49, 99, and 199 receive the same integrity, symmetry, strength,
   tactical, and diversity evaluations. Training loss alone never promotes a
   checkpoint.

The branch becomes a champion candidate only if it retains exact D4 behavior,
shows material match strength, and does not regress on tactical fixtures. The
failed V1 run and the completed D4 fine-tune remain controls rather than being
silently replaced.
