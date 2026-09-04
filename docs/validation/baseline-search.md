# Baseline search validation

Validated on 2026-09-04 with the optimized C++ rules engine.

## Components

- exact negamax/alpha-beta oracle with a transposition table and explicit time/node limits;
- seeded random agent;
- one-ply greedy heuristic agent;
- depth-limited alpha-beta heuristic agent;
- pure Monte Carlo tree search with random rollouts and immediate-win detection;
- paired-color match runner and deterministic round-robin CLI.

## Automated checks

- all tactical agents choose a one-move trapping win in a constructed position;
- the oracle proves that position is a win and returns the trapping action;
- seeded random games reproduce the exact action sequence;
- match accounting covers every game while alternating colors;
- full project suite: 57 tests passed;
- Ruff and strict mypy passed.

## Deterministic smoke tournament

Command:

```powershell
escape-ai benchmark-baselines --games 4 --size 3 --seed 20260904 --mcts-simulations 100
```

Results are wins by the first agent, wins by the second agent, then draws:

| Matchup | Score |
| --- | ---: |
| random vs greedy | 0-2-2 |
| random vs heuristic | 0-3-1 |
| random vs pure-mcts | 0-4-0 |
| greedy vs heuristic | 2-1-1 |
| greedy vs pure-mcts | 0-3-1 |
| heuristic vs pure-mcts | 0-4-0 |

This tiny-board run validates the tournament plumbing and demonstrates nontrivial
strength separation. It is not evidence about 17x17 strategic diversity; that
requires the planned learned-agent leagues and substantially larger samples.
