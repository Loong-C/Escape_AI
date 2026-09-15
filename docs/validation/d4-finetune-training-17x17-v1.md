# D4 champion fine-tune training result

The preregistered lineage C repair completed its full 50,000-game training
budget. This is a training-completion result, not a strength-promotion result;
the final checkpoint still requires frozen symmetry, match, tactical, and
diversity evaluations.

## Reproduction record

- Configuration: `configs/lineages/lineage-c-d4-finetune-17x17-v1.yaml`,
  SHA-256
  `2fe41afc7d48af1d56b6ac1471dfc42dcdff928b3ba42dca1f0c7ad9e71c0821`.
- Git commit used for generation:
  `067027bb89d01a0dcdc58d39ded4825e5db713f2`.
- Seed: `20260917`.
- Parent: lineage C generation 199, SHA-256
  `0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`;
  optimizer state intentionally reset.
- Hardware: NVIDIA GeForce RTX 4060 Ti 8 GB, driver 581.57; Windows 11 build
  26100; PyTorch 2.11.0+cu128, CUDA 12.8.
- Search/training budget: 100 generations × 500 games; 64 PUCT simulations,
  16 parallel leaves; 500 optimizer steps and at most 100,000 sampled replay
  positions per generation; learning rate `0.0005`; random role-aware D4 replay
  augmentation.
- Approximate wall interval: 2026-09-14 13:17:47 to 2026-09-15 00:55:55
  Asia/Shanghai, or 11 h 38 min 08 s.

## Outputs

- 50,000 games, 1,817,562 positions, 500 Parquet shards, 100 checkpoints, and
  77,180,724 compressed replay bytes under `E:\Escape\_AI`.
- Final checkpoint: `generation-0099.pt`, SHA-256
  `999a837cd7f319780016388567e2d7cf9e7c90c1d5d919f043ac06f04295d65d`.
- Progress/data manifest SHA-256:
  `7f3b0ba3cbb4c2bb172d57dd540cabe58855d14b3ec5d0b286b1dd4e244d5468`.
  The manifest records every replay path, byte size, and SHA-256; each
  checkpoint records the hashes of its generation shards.

Losses were finite and smooth. Mean total/policy/value loss changed from
`4.9327/4.4935/0.4392` at generation 0 to
`4.1859/3.8574/0.3285` at generation 99. This establishes successful continued
learning but does not, by itself, establish improved playing strength or
one-view equivariance.
