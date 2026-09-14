# Role-aware D4 training smoke result

The committed 3×3 smoke lineage completed both generations and all eight games
from Git commit `b46d8b784d3bbb14f2cafb211e1fb8573679e75e`. It exercised random role-aware
D4 replay augmentation, learner updates, atomic replay/checkpoint writes, and a
completed-lineage reload.

- Configuration: `configs/lineages/d4-smoke-3x3-v1.yaml`, SHA-256
  `df1fc2dbd95a184d679aaa0e3fb8af72c8ce2791792004d84f8622b05ddf8d8a`.
- Seed: `20260919`.
- Output: 2 generations, 8 games, 138 positions, 4 replay shards, and 24,156
  compressed replay bytes under `E:\Escape\_AI`.
- Final checkpoint:
  `E:\Escape\_AI\checkpoints\lineage-d4-smoke-3x3-v1\generation-0001.pt`,
  SHA-256
  `814925a5a8e1ca530cded081487f24455e35a28876700d7e7495bcad63497c2c`.
- Progress manifest:
  `E:\Escape\_AI\runs\lineage-d4-smoke-3x3-v1\progress.json`, SHA-256
  `3b8387ec94ab91acb3dcb3eedf87108b62e51b61728c5ace0f8ebe70fc1e66f6`.
- Measured first-run wall time: 4.09 seconds on CUDA.

All recorded replay paths, sizes, and hashes matched. Re-running the completed
configuration revalidated the replay and final checkpoint, performed no new
training, and left the progress manifest byte-identical. Unit tests separately
apply all eight transforms to an asymmetric state and verify the role-aware
state, every policy action, legal masks, normalization, and deterministic
seeded sampling. The full quality gates passed: Ruff, mypy over 47 source
files, and 132 pytest tests.

This smoke run validates the mechanics, not 17×17 strength or learned
equivariance. Those remain outcomes of the two preregistered formal lineages
and their later frozen symmetry/league evaluations.
