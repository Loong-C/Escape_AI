# 17×17 role-aware D4 training protocol

The raw-versus-D4 strength match established that an eight-view role-aware D4
ensemble raises lineage C's matched score to 72.825%. This protocol tests
whether the same consistency can be learned into a one-view network and
separates efficient repair of the existing champion from symmetry-native
training from random initialization.

## Frozen augmentation

For each replay row selected for a learner phase, `random-d4` independently and
uniformly selects one of the eight D4 transforms from the learner seed. The C++
rules transform is the source of truth. Rotations and diagonal reflections that
exchange the players' goal axes also exchange White and Black posts and the
side to move. The MCTS policy target is permuted through the same action
transform; the legal mask is recomputed from the transformed state. The value
target is unchanged because it is stored from the current player's perspective,
and the transformed current player represents the same strategic role.

The sampled replay population is not expanded eightfold. Every selected row
contributes exactly one transformed example, keeping memory and optimizer-step
budgets equal to the original lineages. The transform sequence is reproducible
from the committed lineage seed and generation number.

## Branch A: champion repair

`configs/lineages/lineage-c-d4-finetune-17x17-v1.yaml` starts from lineage C
generation 199, SHA-256
`0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`.
The checkpoint is verified before loading. Its optimizer moments are
intentionally discarded to avoid carrying the old `0.002` schedule into the
repair; the fine-tuning learning rate is `0.0005`.

The branch runs 100 generations of 500 games, for 50,000 new self-play games.
Each generation uses 64-simulation PUCT, 500 learner steps, a 100,000-position
sample, and the last 100 replay shards. The first generation self-plays with
the original raw checkpoint; later generations use the newest repaired
one-view network. The branch seed is `20260917`.

## Branch B: symmetry-native training

`configs/lineages/lineage-d-d4-native-17x17-v1.yaml` starts from a new random
network with seed `20260918`. It runs the original full budget of 200
generations × 500 games = 100,000 games. Network, self-play, replay, and learner
budgets match lineages A/B/C; the only training-policy change is role-aware D4
augmentation.

The fresh branch uses learning rate `0.002`. Its generation 99 checkpoint gives
a matched 50,000-game comparison with the final fine-tuned branch, while
generation 199 tests whether a full from-scratch budget ultimately surpasses
repair.

Both branches write replay, checkpoints, and progress only under
`E:\Escape\_AI`. They run sequentially on the single GPU from one clean Git
commit. A shard boundary is the only recovery point; configuration, initial
checkpoint, replay-shard, and checkpoint hashes preserve provenance.

## Pre-run and evaluation gates

Before either 17×17 branch starts, the committed 3×3 D4 smoke lineage must
complete two generations, reload its checkpoint, and show deterministic
role-aware state/policy transforms with normalized legal policy targets. Ruff,
mypy, pytest, and PowerShell parsing must pass.

Training loss is diagnostic, not a promotion criterion. At generations 24,
49, 99, and (for branch B) 199, evaluation will use raw one-view inference and
apply these gates:

1. the frozen stratified symmetry audit measures neural and PUCT equivariance;
2. paired reciprocal-color matches compare against raw lineage C and its D4
   ensemble at fixed search budget;
3. direct fine-tune versus fresh cross-play uses matched seeds and reports
   first/second-player results separately;
4. tactical positions and fixed baselines check for catastrophic forgetting;
5. only models passing integrity, symmetry, strength, and tactical gates can
   become the new champion.

No one-view model is called equivariant merely because it saw augmented data.
The symmetry audit must establish the achieved error empirically. Likewise, a
symmetry improvement that loses material playing strength is retained as an
ablation rather than promoted.
