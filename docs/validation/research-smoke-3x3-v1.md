# Analysis-record smoke run: research-smoke-3x3-v1

Generated on 2026-09-04 from Git commit
`94c10fc33d0d46c9de34cbef5fc643f6932f2a01`, using checkpoint
`3fcc1787f563b586` and 32 PUCT simulations per move.

## Data integrity

- four games and 44 detailed move rows in two Parquet shards;
- every row includes reconstructible state bytes, state hash, actual action,
  directional costs, structural counts, candidate P/N/Q, and final result;
- DuckDB read both shards directly;
- the resumable runner returned without overwrite on a second invocation.

## Smoke observations

- all four games were black wins by escape after 11 plies;
- first ball movement occurred at ply 9;
- the set contains eight replacements, eight ball moves, and four positions with
  reply-resistance `R=0`;
- mean root policy entropy was 2.433 nats;
- all games chose the same opening and followed the same line.

The last point is expected because this smoke configuration used deterministic
selection, no root noise, one checkpoint, and an identical initial position.
It is evidence that repeated deterministic games carry no diversity information,
not evidence that Escape itself lacks strategic diversity. The research generator
now supports a seeded opening-exploration window followed by deterministic
high-budget play; formal 10,000-game competition and 1,000-game analysis configs
must enable that window or provide an explicit opening suite.

The generated analysis is stored at
`G:\Escape\_AI\runs\research-smoke-3x3-v1\analysis.json`.
