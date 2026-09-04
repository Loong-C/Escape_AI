# Neural encoding and PUCT validation

Validated on 2026-09-04 with PyTorch 2.11.0+cu128 and an NVIDIA RTX 4060 Ti.

## Implemented core

- six canonical feature planes: white posts, black posts, ball cell corners,
  horizontal walls, vertical walls, and side to move;
- D4-equivariant geometry, including color/axis swaps for quarter turns and
  diagonal reflections;
- fully convolutional residual policy-value network supporting all configured
  odd board sizes without changing parameters;
- legal-action-masked, batched Torch evaluator;
- PUCT with root Dirichlet noise, temperature sampling, action statistics, and
  value propagation based on actual parent/child player identities.

The explicit player comparison during backup matters because an Escape terminal
state retains the player who made the final move instead of switching turns.

## Verification

- encoder feature, legal-mask, and all-eight-symmetry equivalence tests passed;
- one network instance produced correctly shaped policy/value outputs for 3x3
  and 17x17 boards;
- masked priors normalized to one over exactly the legal actions;
- uniform-prior PUCT found and positively valued a constructed immediate win;
- full project quality gates passed.

The default 6-block, 64-channel network has 450,948 parameters. A local synthetic
batch-128 benchmark on 17x17 inputs processed about 33,845 positions/second after
warmup. This measures network throughput only, not end-to-end tree search.
