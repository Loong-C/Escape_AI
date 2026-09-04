from __future__ import annotations

import random
from dataclasses import replace

import pytest

from escape_ai.game import (
    AXIS_SWAPPING_SYMMETRIES,
    Cell,
    Direction,
    Outcome,
    Player,
    Symmetry,
    WinReason,
    apply_action,
    create_game,
    deserialize_state,
    list_legal_moves,
    serialize_state,
    set_post,
    transform_action,
    transform_direction,
    transform_player,
    transform_state,
)


def canonical(state: object) -> object:
    return replace(state, last_move=None)  # type: ignore[arg-type]


def test_canonical_state_serialization_is_stable() -> None:
    state = create_game(5)
    rng = random.Random(7)
    for _ in range(10):
        state = apply_action(state, rng.choice(list_legal_moves(state)).action)
        if state.outcome.status.value != "playing":
            break
    serialized = serialize_state(state)
    assert serialize_state(deserialize_state(serialized)) == serialized
    assert deserialize_state(serialized) == canonical(state)


@pytest.mark.parametrize("symmetry", list(Symmetry))
def test_every_symmetry_is_its_expected_inverse(symmetry: Symmetry) -> None:
    inverse = {
        Symmetry.ROTATE_90: Symmetry.ROTATE_270,
        Symmetry.ROTATE_270: Symmetry.ROTATE_90,
    }.get(symmetry, symmetry)
    state = set_post(create_game(5), 1, 2, Player.WHITE)
    state = set_post(state, 4, 3, Player.BLACK)
    restored = transform_state(transform_state(state, symmetry), inverse)
    assert restored == state


@pytest.mark.parametrize("symmetry", list(Symmetry))
def test_d4_preserves_legal_transitions(symmetry: Symmetry) -> None:
    state = set_post(create_game(5), 1, 2, Player.WHITE)
    state = set_post(state, 3, 4, Player.BLACK)
    action = list_legal_moves(state)[8].action
    expected = transform_state(apply_action(state, action), symmetry)
    actual = apply_action(
        transform_state(state, symmetry),
        transform_action(action, state.size, symmetry),
    )
    assert canonical(actual) == expected


def test_axis_swapping_symmetries_swap_player_roles() -> None:
    for symmetry in Symmetry:
        expected = Player.BLACK if symmetry in AXIS_SWAPPING_SYMMETRIES else Player.WHITE
        assert transform_player(Player.WHITE, symmetry) is expected


def test_exit_winner_and_direction_transform_together() -> None:
    state = replace(
        create_game(3),
        ball=Cell(1, 2),
        outcome=Outcome.won(Player.WHITE, WinReason.ESCAPED, Direction.RIGHT),
    )
    transformed = transform_state(state, Symmetry.ROTATE_90)
    assert transformed.outcome.winner is Player.BLACK
    assert transformed.outcome.exit_direction is transform_direction(
        Direction.RIGHT,
        Symmetry.ROTATE_90,
    )
