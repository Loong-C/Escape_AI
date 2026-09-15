# Canonical-D4 training smoke result

The canonical inference/training path completed both 3×3 generations and all
eight games from Git commit
`718d698db14e89df43ce4cd0cbb41ae6aaa6ca15`.

- Configuration: `configs/lineages/canonical-d4-smoke-3x3-v1.yaml`, SHA-256
  `c731a017b76279e1ee83867e105847566f61ac33c25774a0493a3a35d3713381`.
- Seed: `20260920`; evaluator and learner mode: `canonical-d4`.
- Output: 2 generations, 8 games, 123 positions, 4 replay shards, and 24,844
  compressed replay bytes under `E:\Escape\_AI`.
- Final checkpoint: `generation-0001.pt`, SHA-256
  `9801a716f76d9e8a68258bca4dbaa49d9013105688eebdfebf436334a97e2c32`.
- Progress manifest SHA-256:
  `0d0fb18ce624042b05ccd6a47be33994c82752d251cfe46e9540201038d66f93`.
- First-run wall time: 4.74 seconds on CUDA.

A completed-lineage rerun reloaded and validated the recorded artifacts,
performed no additional self-play or learning, and left the progress manifest
byte-identical. The complete quality suite passed: Ruff, strict mypy over 47
source files, and 140 pytest tests. Unit tests additionally establish exact
policy equivariance across all eight role-aware D4 transforms for asymmetric
and stabilizer-symmetric states, one base-network call per distinct orbit,
normalized legal policies, and source-orientation-independent canonical replay
targets.

This validates mechanics and resumability only. The 17×17 bootstrap gate and
later strength/tactical evaluations remain empirical requirements.
