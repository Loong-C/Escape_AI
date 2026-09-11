# 17×17 champion first-player diagnostic protocol

The official rule binds the first player to White and the second player to
Black. Because White's exits are horizontal and Black's are vertical, a square
board is exactly symmetric under a 90° rotation combined with exchanging roles.
The raw checkpoint broke this equivalence; the validated D4 ensemble does not.

This diagnostic therefore contains two explicitly labeled arms:

- 1,000 official games with White to move first;
- 1,000 non-rule diagnostic games with Black to move first.

`configs/games/champion-first-player-diagnostic-17x17-v1.yaml` interleaves the
two arms and assigns the same seed to each adjacent pair. Seeds are exactly
`20260912` through `20261911`, matching the original 1,000-game champion
analysis. Both colors use the lineage-C generation-199 checkpoint through the
validated role-aware D4 ensemble.

Each pair is evaluated in one actor batch. If the entire game state remains
role-swapped equivalent, ensemble evaluation deduplicates the two D4 orbits;
this makes the Black-first validation arm much cheaper than an independent
second run. Every game uses 512 PUCT simulations, 16 parallel leaves,
temperature 0.8 through ply 19 and zero thereafter, no root noise, and saves
the top 16 candidates plus reply-resistance features.

The formal run generates 2,000 games in 100 atomic 20-game shards under
`E:\Escape\_AI\games\champion-first-player-diagnostic-17x17-v1`. It can resume
only from a matching clean Git commit and configuration hash. The progress
manifest belongs at
`E:\Escape\_AI\runs\champion-first-player-diagnostic-17x17-v1\progress.json`.

After generation, `analyze-first-player` verifies every paired pre-move state,
action, winner, reason, and game length under all four role-swapping D4
transforms. Statistical inference uses only the 1,000 official White-first
games; the Black-first games are deterministic mirrored validation pairs, not
independent observations. The report will record first-player wins, draws,
decisive win rate, Wilson 95% interval, and an exact two-sided binomial test
against 50%.

Interpretation is pre-registered:

- all 1,000 pairs must mirror exactly; otherwise the pipeline returns to search
  or evaluator debugging;
- if they mirror, any White advantage in the official arm is a first-player
  effect for this symmetric agent and board, not a horizontal-axis advantage;
- the size and uncertainty of that effect determine whether later strategy
  studies need balanced openings, swap rules, or separate first/second-player
  policy populations.
