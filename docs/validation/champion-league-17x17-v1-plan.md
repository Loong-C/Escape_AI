# 17×17 champion league protocol

The three final checkpoints from independent lineages A, B, and C enter an
exact 10,000-game round robin. The committed configuration is
`configs/leagues/champion-17x17-v1.yaml`.

- Every matchup receives complete color pairs. The exact budget is distributed
  as 3,334, 3,334, and 3,332 games across the three pairings.
- Both color legs of a pair use the same seed. The first 16 plies use
  temperature 0.8 to sample from search visits; all later moves are
  deterministic. Root noise is disabled.
- Competition search uses 128 PUCT simulations per move, twice the 64-simulation
  training budget, with batched CUDA inference and 16 parallel leaves.
- Atomic 100-game JSONL/Gzip shards preserve actions and outcomes under
  `E:\Escape\_AI\games\champion-league-17x17-v1`.
- `progress.json` records the Git commit, configuration hash, checkpoint hashes,
  per-matchup results, and shard hashes. Resume is accepted only when those
  identities match.
- The champion is the entrant with the highest total cross-play score rate;
  wins and then stable agent ID order break exact ties. Pairwise Wilson intervals
  remain in the final matrix so a narrow ranking is not overstated as a
  statistically decisive superiority claim.

The result report will be committed only after all 10,000 games finish and the
machine-readable final matrix has been checked.
