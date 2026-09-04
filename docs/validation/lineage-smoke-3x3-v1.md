# Resumable lineage smoke run: lineage-smoke-3x3-v1

Run on 2026-09-04 from Git commit `e8ab0deb166b2717458a14badbfbf127cc6b0b63`
with the committed `configs/lineages/smoke-3x3-v1.yaml` configuration.

## Outcome

- two generations and eight self-play games completed;
- four atomic Parquet shards contain 143 positions and two distinct model IDs;
- generation 0 checkpoint: `3fe61e166dcbcb21`, SHA-256
  `3fe61e166dcbcb21b867382ea07631a07083bc0a0a6e2a25721ed92408715ab3`;
- generation 1 checkpoint: `3fcc1787f563b586`, SHA-256
  `3fcc1787f563b5861b8da8a515b1fa00762cf9bb7210e423d7ca8d9ce939c851`;
- generation mean loss moved from 2.84804 to 2.57956 in this plumbing-scale run;
- first execution took 3.36 seconds.

The progress manifest is
`G:\Escape\_AI\runs\lineage-smoke-3x3-v1\progress.json`. A second invocation
verified the committed config hash, Git commit, replay manifest, and final
checkpoint, then returned the completed result in under one millisecond without
regenerating or overwriting artifacts.

This validates generation transitions, bounded replay sampling, optimizer-state
continuation, checkpoint chaining, and completed-run resumption. It does not
measure model strength.
