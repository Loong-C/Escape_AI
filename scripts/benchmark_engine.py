"""Compare complete-game throughput of the Python and C++ rules engines."""

from __future__ import annotations

import argparse
import json
import random
import time
from collections.abc import Callable

from escape_ai.game.optimized import create_core_state
from escape_ai.game.reference import apply_action, create_game, list_legal_moves
from escape_ai.game.types import OutcomeStatus


def benchmark_reference(size: int, games: int, seed: int) -> tuple[float, int]:
    rng = random.Random(seed)
    plies = 0
    started = time.perf_counter()
    for _ in range(games):
        state = create_game(size)
        while state.outcome.status is OutcomeStatus.PLAYING:
            move = rng.choice(list_legal_moves(state))
            state = apply_action(state, move.action)
            plies += 1
    return time.perf_counter() - started, plies


def benchmark_core(size: int, games: int, seed: int) -> tuple[float, int]:
    rng = random.Random(seed)
    plies = 0
    started = time.perf_counter()
    for _ in range(games):
        state = create_core_state(size)
        while state.outcome["status"] == "playing":
            action = rng.choice(state.legal_actions())
            state = state.apply(action)
            plies += 1
    return time.perf_counter() - started, plies


def run_benchmark(
    benchmark: Callable[[int, int, int], tuple[float, int]],
    size: int,
    games: int,
    seed: int,
) -> tuple[float, int]:
    elapsed, plies = benchmark(size, games, seed)
    if elapsed <= 0:
        raise RuntimeError("benchmark timer did not advance")
    return elapsed, plies


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=17)
    parser.add_argument("--games", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260904)
    args = parser.parse_args()

    reference_seconds, reference_plies = run_benchmark(
        benchmark_reference, args.size, args.games, args.seed
    )
    core_seconds, core_plies = run_benchmark(benchmark_core, args.size, args.games, args.seed)
    if reference_plies != core_plies:
        raise AssertionError("engines followed different deterministic trajectories")
    print(
        json.dumps(
            {
                "size": args.size,
                "games": args.games,
                "plies": reference_plies,
                "python_seconds": reference_seconds,
                "cpp_seconds": core_seconds,
                "speedup": reference_seconds / core_seconds,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
