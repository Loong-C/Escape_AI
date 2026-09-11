# 17×17 champion analysis protocol

The 10,000-game final-checkpoint league selected lineage C as champion with a
70.03% aggregate cross-play score. This protocol locks checkpoint SHA-256
`0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3`
before producing any analysis games.

The committed `configs/games/champion-analysis-17x17-v1.yaml` configuration
generates 1,000 games with the same champion controlling both colors. Each move
uses 512 PUCT simulations—eight times the training budget and four times the
championship budget. The first 20 plies sample at temperature 0.8 without root
noise; later play is deterministic. This preserves a controlled opening sample
while keeping tactical continuation at the full analysis budget.

Every move stores reconstructible state, candidate P/N/Q values, root value,
directional distances, structural counts, replacements, ball movement, and
reply resistance. Twenty games form an atomic Parquet shard under
`E:\Escape\_AI\games\champion-analysis-17x17-v1`; progress and the DuckDB
summary remain under `E:\Escape\_AI\runs\champion-analysis-17x17-v1`.

The post-run report will examine:

- color balance with player strength held constant;
- D4-canonical opening-prefix entropy at 1, 3, 5, 10, and 20 plies;
- first-ball-movement timing and the structure present at that moment;
- replacements, forced gradient sequences, reply resistance, and candidate
  value gaps;
- phase-dependent entropy, legal-action counts, and value confidence;
- evidence for both strategic diversity and selective convergence, with clear
  limits on claims that require still higher-budget tactical re-search.
