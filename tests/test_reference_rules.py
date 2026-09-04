from __future__ import annotations

from dataclasses import replace
from math import inf

import pytest

from escape_ai.game import (
    Cell,
    Direction,
    DirectionalDistances,
    MoveKind,
    OutcomeStatus,
    Player,
    WinReason,
    adjudicate_turn_start,
    apply_move,
    create_game,
    directional_exit_distances,
    first_step_costs,
    get_post,
    is_anchored,
    is_passage_blocked,
    legal_move,
    list_walls,
    set_post,
    shortest_escape,
    vertex_index,
)


def place_many(
    state: object,
    entries: list[tuple[int, int, Player]],
) -> object:
    current = state
    for row, col, player in entries:
        current = set_post(current, row, col, player)  # type: ignore[arg-type]
    return current


def right_corridor_state(ball_col: int = 2):
    state = replace(create_game(5), ball=Cell(2, ball_col))
    entries: list[tuple[int, int, Player]] = []
    for col in range(state.size + 1):
        entries.append((0, col, Player.BLACK))
        entries.append((state.size, col, Player.WHITE))
    for row in range(1, state.size):
        entries.append((row, 0, Player.BLACK))
    return place_many(state, entries)


def test_starts_a_17_by_17_board_in_the_geometric_center() -> None:
    state = create_game()
    assert state.ball == Cell(8, 8)
    assert len(state.posts) == 324
    assert directional_exit_distances(state) == DirectionalDistances(9, 9, 9, 9)
    assert first_step_costs(state) == DirectionalDistances(9, 9, 9, 9)


@pytest.mark.parametrize("size", [3, 5, 7, 9, 11, 13, 15, 17])
def test_accepts_supported_odd_sizes(size: int) -> None:
    assert create_game(size).size == size


@pytest.mark.parametrize("size", [0, 2, 4, 18, 19])
def test_rejects_unsupported_sizes(size: int) -> None:
    with pytest.raises(ValueError):
        create_game(size)


def test_forms_walls_between_orthogonally_adjacent_matching_posts() -> None:
    state = place_many(
        create_game(3),
        [(1, 1, Player.WHITE), (1, 2, Player.WHITE)],
    )
    assert any(
        wall.orientation == "horizontal" and wall.row == 1 and wall.col == 1
        for wall in list_walls(state)
    )
    assert is_passage_blocked(state, Cell(0, 1), Direction.DOWN)
    assert is_passage_blocked(state, Cell(1, 1), Direction.UP)


def test_distinguishes_floating_and_anchored_posts() -> None:
    state = set_post(create_game(3), 1, 1, Player.BLACK)
    assert not is_anchored(state, 1, 1)
    state = set_post(state, 1, 2, Player.BLACK)
    assert is_anchored(state, 1, 1)
    assert is_anchored(state, 1, 2)


def test_replaces_only_an_opponent_floating_post_that_forms_a_wall() -> None:
    state = place_many(
        create_game(3),
        [(2, 2, Player.BLACK), (2, 1, Player.WHITE)],
    )
    action = vertex_index(state.size, 2, 2)
    move = legal_move(state, action)
    assert move is not None and move.kind is MoveKind.REPLACE
    next_state = apply_move(state, 2, 2)
    assert get_post(next_state, 2, 2) is Player.WHITE


def test_does_not_replace_an_anchored_post() -> None:
    state = place_many(
        create_game(3),
        [
            (1, 1, Player.BLACK),
            (1, 2, Player.BLACK),
            (2, 1, Player.WHITE),
        ],
    )
    assert legal_move(state, vertex_index(state.size, 1, 1)) is None


def test_ball_stays_when_several_shortest_first_steps_tie() -> None:
    state = create_game(3)
    next_state = apply_move(state, 0, 0)
    assert next_state.ball == state.ball
    assert next_state.last_move is not None
    assert next_state.last_move.shortest.first_steps == (
        Direction.UP,
        Direction.RIGHT,
        Direction.DOWN,
        Direction.LEFT,
    )


def test_ball_moves_exactly_once_for_a_unique_shortest_first_step() -> None:
    state = right_corridor_state()
    assert shortest_escape(state).first_steps == (Direction.RIGHT,)
    next_state = apply_move(state, 2, 3)
    assert next_state.ball == Cell(2, 3)
    assert next_state.ply == 1


def test_counts_the_boundary_crossing_and_marks_blocked_steps_infinite() -> None:
    state = right_corridor_state()
    assert directional_exit_distances(state) == DirectionalDistances(
        up=inf,
        right=3,
        down=inf,
        left=5,
    )


def test_direct_exit_first_step_cost_is_one() -> None:
    state = replace(create_game(3), ball=Cell(1, 2))
    costs = first_step_costs(state)
    assert costs.right == 1
    assert costs.up == 2
    assert shortest_escape(state).first_steps == (Direction.RIGHT,)


def test_mover_wins_when_the_ball_becomes_trapped() -> None:
    state = place_many(
        create_game(3),
        [
            (1, 1, Player.WHITE),
            (1, 2, Player.WHITE),
            (2, 1, Player.WHITE),
        ],
    )
    next_state = apply_move(state, 2, 2)
    assert next_state.outcome.status is OutcomeStatus.WON
    assert next_state.outcome.winner is Player.WHITE
    assert next_state.outcome.reason is WinReason.TRAPPED


def test_boundary_owner_wins_even_when_the_other_player_moves() -> None:
    state = replace(create_game(3), ball=Cell(1, 2), turn=Player.BLACK)
    next_state = apply_move(state, 0, 0)
    assert next_state.outcome.status is OutcomeStatus.WON
    assert next_state.outcome.winner is Player.WHITE
    assert next_state.outcome.reason is WinReason.ESCAPED
    assert next_state.outcome.exit_direction is Direction.RIGHT
    assert next_state.last_move is not None and next_state.last_move.ball_after is None


def test_draws_when_the_player_to_move_has_no_legal_action() -> None:
    state = create_game(3)
    full = replace(state, posts=(Player.WHITE,) * len(state.posts))
    adjudicated = adjudicate_turn_start(full)
    assert adjudicated.outcome.status is OutcomeStatus.DRAW
    assert adjudicated.outcome.reason is WinReason.NO_LEGAL_MOVES
