# League smoke run: league-smoke-3x3-v1

Run on 2026-09-04 from Git commit `aecd6aa4c33ae21a297a1e8b3632ce1d4c16ac6e`
using the committed `configs/leagues/smoke-3x3-v1.yaml` configuration and
checkpoint `f024480c870569dd`.

The complete five-agent round robin contained 10 color-paired matchups and 80
games. Scores count a draw as one half-point.

| First agent | Second agent | W-L-D | First score | 95% interval |
| --- | --- | ---: | ---: | ---: |
| neural PUCT | random | 5-0-3 | 81.25% | 46.68%-95.55% |
| neural PUCT | greedy | 2-1-5 | 56.25% | 25.89%-82.55% |
| neural PUCT | heuristic | 0-0-8 | 50.00% | 21.52%-78.48% |
| neural PUCT | pure MCTS | 2-5-1 | 31.25% | 10.24%-64.42% |
| random | greedy | 2-5-1 | 31.25% | 10.24%-64.42% |
| random | heuristic | 0-8-0 | 0.00% | 0.00%-32.44% |
| random | pure MCTS | 0-7-1 | 6.25% | 0.66%-40.23% |
| greedy | heuristic | 3-1-4 | 62.50% | 30.57%-86.32% |
| greedy | pure MCTS | 1-4-3 | 31.25% | 10.24%-64.42% |
| heuristic | pure MCTS | 0-3-5 | 31.25% | 10.24%-64.42% |

The machine-readable result is at
`G:\Escape\_AI\runs\league-smoke-3x3-v1\league.json`. No confidence interval
for the neural checkpoint clears a 50% promotion threshold. The result therefore
validates cross-play, color pairing, uncertainty reporting, and model loading; it
does not claim meaningful trained strength from four self-play games.
