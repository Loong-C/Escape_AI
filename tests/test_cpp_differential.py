from __future__ import annotations

from escape_ai import _escape_core
from escape_ai.game.differential import assert_engines_equal, run_differential_validation
from escape_ai.game.optimized import (
    SYMMETRY_TO_CORE,
    core_snapshot,
    create_core_state,
    reference_snapshot,
)
from escape_ai.game.reference import apply_action, create_game, list_legal_moves
from escape_ai.game.symmetry import transform_state
from escape_ai.game.types import Symmetry


def test_cpp_core_matches_the_empty_standard_board() -> None:
    assert_engines_equal(create_game(), create_core_state())


def test_cpp_apply_in_place_can_be_undone_exactly() -> None:
    state = create_core_state(5)
    before = state.serialize()
    before_hash = state.hash()
    token = state.apply_in_place(0)
    state.undo(token)
    assert state.serialize() == before
    assert state.hash() == before_hash


def test_cpp_d4_matches_reference_after_a_short_trajectory() -> None:
    reference = create_game(5)
    core = create_core_state(5)
    for _ in range(7):
        action = list_legal_moves(reference)[-1].action
        reference = apply_action(reference, action)
        core = core.apply(action)
    for symmetry in Symmetry:
        assert reference_snapshot(transform_state(reference, symmetry)) == core_snapshot(
            core.transformed(SYMMETRY_TO_CORE[symmetry])
        )


def test_random_complete_games_match_between_engines() -> None:
    summary = run_differential_validation(
        games_per_size=2,
        sizes=(3, 5, 9, 17),
        seed=20260904,
    )
    assert summary.games == 8
    assert summary.states > summary.games
    assert summary.plies > 0


def test_cpp_module_exposes_the_infinity_sentinel() -> None:
    assert _escape_core.INFINITY_DISTANCE > 17 * 17
