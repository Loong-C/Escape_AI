"""Cross-engine randomized validation for the Python and C++ rules implementations."""

from __future__ import annotations

import random
from dataclasses import dataclass

from escape_ai import _escape_core

from .optimized import (
    SYMMETRY_TO_CORE,
    core_costs,
    core_exit_distances,
    core_snapshot,
    create_core_state,
    reference_snapshot,
)
from .reference import (
    apply_action,
    create_game,
    directional_exit_distances,
    first_step_costs,
    is_anchored,
    list_legal_moves,
    list_walls,
    shortest_escape,
)
from .symmetry import transform_action, transform_state
from .types import GameState, OutcomeStatus, Symmetry


@dataclass(frozen=True, slots=True)
class DifferentialSummary:
    seed: int
    sizes: tuple[int, ...]
    games: int
    states: int
    plies: int


def _normalized_reference_walls(state: GameState) -> list[tuple[str, int, int, str]]:
    return sorted(
        (wall.orientation, wall.row, wall.col, wall.color.value) for wall in list_walls(state)
    )


def assert_engines_equal(reference: GameState, core: _escape_core.State) -> None:
    if reference_snapshot(reference) != core_snapshot(core):
        raise AssertionError(
            f"canonical state mismatch\nreference={reference_snapshot(reference)!r}\n"
            f"core={core_snapshot(core)!r}"
        )

    reference_moves = list_legal_moves(reference)
    reference_actions = [move.action for move in reference_moves]
    if reference_actions != core.legal_actions():
        raise AssertionError("legal action mismatch")
    for move in reference_moves:
        if move.kind.value != core.legal_move_kind(move.action):
            raise AssertionError(f"legal move kind mismatch at action {move.action}")

    if first_step_costs(reference).as_tuple() != core_costs(core):
        raise AssertionError("first-step cost mismatch")
    if directional_exit_distances(reference).as_tuple() != core_exit_distances(core):
        raise AssertionError("directional exit distance mismatch")
    if _normalized_reference_walls(reference) != sorted(core.walls()):
        raise AssertionError("wall set mismatch")

    reference_shortest = shortest_escape(reference)
    core_shortest = core.shortest_escape()
    core_distance = int(core_shortest["distance"])
    normalized_core_distance = (
        float("inf") if core_distance >= _escape_core.INFINITY_DISTANCE else float(core_distance)
    )
    if reference_shortest.distance != normalized_core_distance:
        raise AssertionError("shortest escape distance mismatch")
    if [direction.value for direction in reference_shortest.first_steps] != list(
        core_shortest["first_steps"]
    ):
        raise AssertionError("shortest escape first-step mismatch")

    for row in range(reference.size + 1):
        for col in range(reference.size + 1):
            if is_anchored(reference, row, col) != core.is_anchored(row, col):
                raise AssertionError(f"anchor mismatch at ({row}, {col})")


def run_differential_validation(
    *,
    games_per_size: int,
    sizes: tuple[int, ...],
    seed: int,
) -> DifferentialSummary:
    rng = random.Random(seed)
    total_games = 0
    total_states = 0
    total_plies = 0

    for size in sizes:
        for _ in range(games_per_size):
            reference = create_game(size)
            core = create_core_state(size)
            while True:
                assert_engines_equal(reference, core)
                total_states += 1

                restored = _escape_core.State.deserialize(core.serialize())
                if core_snapshot(restored) != core_snapshot(core) or restored.hash() != core.hash():
                    raise AssertionError("C++ binary state serialization did not round-trip")

                symmetry = rng.choice(tuple(Symmetry))
                transformed_reference = transform_state(reference, symmetry)
                transformed_core = core.transformed(SYMMETRY_TO_CORE[symmetry])
                if reference_snapshot(transformed_reference) != core_snapshot(transformed_core):
                    raise AssertionError(f"C++ D4 state mismatch for {symmetry.value}")

                if reference.outcome.status is not OutcomeStatus.PLAYING:
                    break
                move = rng.choice(list_legal_moves(reference))
                if transform_action(move.action, size, symmetry) != _escape_core.transform_action(
                    move.action,
                    size,
                    SYMMETRY_TO_CORE[symmetry],
                ):
                    raise AssertionError(f"C++ D4 action mismatch for {symmetry.value}")
                reference = apply_action(reference, move.action)
                core = core.apply(move.action)
                total_plies += 1
            total_games += 1

    return DifferentialSummary(seed, sizes, total_games, total_states, total_plies)
