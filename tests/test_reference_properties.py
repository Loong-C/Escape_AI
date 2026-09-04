from __future__ import annotations

import random
from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from escape_ai.game import (
    OutcomeStatus,
    Player,
    apply_action,
    create_game,
    is_anchored,
    list_legal_moves,
    list_walls,
)


@given(
    size=st.sampled_from([3, 5, 7]),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
@settings(max_examples=60, deadline=None)
def test_random_games_preserve_monotonic_walls_and_length_bound(size: int, seed: int) -> None:
    rng = random.Random(seed)
    state = create_game(size)
    while state.outcome.status is OutcomeStatus.PLAYING:
        moves = list_legal_moves(state)
        assert moves
        anchored_before = {
            (row, col, state.posts[row * (size + 1) + col])
            for row in range(size + 1)
            for col in range(size + 1)
            if is_anchored(state, row, col)
        }
        walls_before = set(list_walls(state))
        state = apply_action(state, rng.choice(moves).action)
        assert walls_before.issubset(set(list_walls(state)))
        assert all(
            state.posts[row * (size + 1) + col] is player for row, col, player in anchored_before
        )
        assert state.ply <= 2 * (size + 1) ** 2


def test_a_replaced_post_immediately_becomes_anchored() -> None:
    state = create_game(3)
    posts = list(state.posts)
    posts[1 * 4 + 1] = Player.WHITE
    posts[1 * 4 + 2] = Player.BLACK
    state = replace(state, posts=tuple(posts))
    move = next(move for move in list_legal_moves(state) if move.row == 1 and move.col == 2)
    next_state = apply_action(state, move.action)
    assert is_anchored(next_state, 1, 2)
