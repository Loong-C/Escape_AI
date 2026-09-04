# AlphaZero pipeline smoke run: az-smoke-3x3-v1

Run on 2026-09-04 from Git commit `afb4add00a095a77ab8bf16ca8cf42059e9c7a8b`
with the committed `configs/experiments/az-smoke-3x3.yaml` configuration.

## Outcome

- hardware: NVIDIA GeForce RTX 4060 Ti, PyTorch 2.11.0+cu128;
- self-play: 4 games, 60 positions, 32 PUCT simulations per move;
- results: 2 draws by no legal moves and 2 white wins by escape;
- learner: 20 steps / 600 sampled positions;
- mean total loss: 2.34364;
- mean policy loss: 2.04685;
- mean value loss: 0.29679;
- elapsed time: 5.51 seconds.

Artifacts are outside Git under `G:\Escape\_AI`:

- replay shard 0: 32 positions, SHA-256
  `ad96930dda1e82f4c63b39afb91cf9f9d998c6dd5b2722ced0f2029ba22f08c6`;
- replay shard 1: 28 positions, SHA-256
  `62bcf60aa2170d12b850332afc59fe24fffc9f073c1c7aae473cc7b8744688bf`;
- checkpoint: 738,181 bytes, SHA-256
  `f024480c870569ddf16325f57bbec8e94b5f385c91b4975aaefc0b4e26f10877`;
- full machine-readable manifest:
  `G:\Escape\_AI\runs\az-smoke-3x3-v1\manifest.json`.

DuckDB read both Parquet shards as four distinct games and 60 rows. The saved
checkpoint was reloaded with the restricted weights-only loader and produced a
normalized 16-action masked policy on CUDA. This run validates plumbing and
reproducibility only; its four games do not establish playing strength.
