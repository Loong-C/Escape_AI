# Formal-shape pilot: pilot-17x17-v1

Date: 2026-09-04

Commit: `dece3952bbbec7a1666bc44e46aea26899b96110`

This pilot exercised the same 64-channel, six-block network and 64-simulation
PUCT search used by the production lineages. Sixteen 17 by 17 games were
generated as one CUDA actor batch, followed by 20 learner steps.

## Results

- Runtime: 34.6748 seconds, including self-play, Parquet output, and learning.
- Positions: 2,521; 72.7 positions/second end to end.
- Game length: minimum 79, mean 157.56, maximum 233 plies.
- Outcome: white 9 wins, black 7 wins.
- Replay: 131,658 bytes, SHA-256
  `bb1c4e7ee7bcd1c777de89e753fcf47a0a05147d8ebebbd7f2804b3ae4d051fd`.
- Checkpoint: 5,476,237 bytes, SHA-256
  `a0b66c8aa9265503bb9b580cd40c24a602d8ea1b065163e53f3a7b7ac4b17236`.
- Mean loss: 6.52538; policy 5.50595; value 1.01942.

The run completed without illegal states, CUDA memory failures, or partial
artifacts. The 16-game outcome split is a pipeline sanity check only and is not
evidence about first-player balance. Production conclusions require trained
cross-play and paired-color games.

The complete machine, config, Git, shard, learner, and checkpoint provenance is
stored at `G:\Escape\_AI\runs\pilot-17x17-v1\manifest.json`.
