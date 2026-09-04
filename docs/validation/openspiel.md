# OpenSpiel adapter validation

Validated on 2026-09-04 with OpenSpiel 2.0.2.

## Design

`python_escape_ai` is a deterministic, sequential, zero-sum, perfect-information
OpenSpiel game. Its state wrapper owns an optimized C++ `State`; legal actions,
transitions, terminal detection, and returns are never reimplemented in the
adapter. C++ state snapshots support Python pickling so OpenSpiel can clone states
without aliasing them.

## Evidence

- OpenSpiel's `random_sim_test` passed on 3x3, 5x5, 9x9, and 17x17.
- Deterministic mirrored runs covered 80 games, 5,860 states, and 5,780 plies with
  identical legal action lists and binary state snapshots after every transition.
- OpenSpiel's reference Python MCTS successfully cloned and searched the adapter.
- The full project suite passed: CTest, Ruff, strict mypy, and 61 pytest tests.

Reproduction command:

```powershell
escape-ai validate-openspiel --games 20 --sizes 3,5,9,17 --seed 20260904
```
