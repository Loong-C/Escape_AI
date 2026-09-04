"""Human-interpretable strategic features derived from canonical states."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from escape_ai import _escape_core


@dataclass(frozen=True, slots=True)
class PositionFeatures:
    ball_row: int
    ball_col: int
    legal_actions: int
    white_posts: int
    black_posts: int
    white_floating: int
    black_floating: int
    white_anchored: int
    black_anchored: int
    white_walls: int
    black_walls: int
    first_step_costs: tuple[int, int, int, int]
    directional_exit_distances: tuple[int, int, int, int]
    unique_gradient: bool
    gradient_delta: int | None


@dataclass(frozen=True, slots=True)
class TransitionFeatures:
    move_kind: str
    new_walls: int
    ball_moved: bool
    ball_move_direction: str | None
    reply_resistance: int | None


def _post_counts(state: _escape_core.State) -> tuple[int, int, int, int]:
    width = state.size + 1
    posts = np.asarray(state.posts, dtype=object).reshape((width, width))
    white = posts == "white"
    black = posts == "black"
    anchored = np.zeros((width, width), dtype=np.bool_)
    vertical_match = (posts[:-1] == posts[1:]) & (posts[:-1] != None)  # noqa: E711
    horizontal_match = (posts[:, :-1] == posts[:, 1:]) & (posts[:, :-1] != None)  # noqa: E711
    anchored[:-1] |= vertical_match
    anchored[1:] |= vertical_match
    anchored[:, :-1] |= horizontal_match
    anchored[:, 1:] |= horizontal_match
    white_count = int(white.sum())
    black_count = int(black.sum())
    white_anchored = int((anchored & white).sum())
    black_anchored = int((anchored & black).sum())
    return white_count, black_count, white_anchored, black_anchored


def position_features(state: _escape_core.State) -> PositionFeatures:
    white, black, white_anchored, black_anchored = _post_counts(state)
    walls = state.walls()
    white_walls = sum(color == "white" for _orientation, _row, _col, color in walls)
    black_walls = len(walls) - white_walls
    costs = tuple(state.first_step_costs())
    exits = tuple(state.directional_exit_distances())
    if len(costs) != 4 or len(exits) != 4:
        raise AssertionError("directional distance vectors must have four entries")
    ordered = sorted(costs)
    unique_gradient = ordered[0] < ordered[1]
    gradient_delta = (
        ordered[1] - ordered[0]
        if unique_gradient and ordered[1] < _escape_core.INFINITY_DISTANCE
        else None
    )
    ball_row, ball_col = state.ball
    return PositionFeatures(
        ball_row,
        ball_col,
        len(state.legal_actions()),
        white,
        black,
        white - white_anchored,
        black - black_anchored,
        white_anchored,
        black_anchored,
        white_walls,
        black_walls,
        (int(costs[0]), int(costs[1]), int(costs[2]), int(costs[3])),
        (int(exits[0]), int(exits[1]), int(exits[2]), int(exits[3])),
        unique_gradient,
        gradient_delta,
    )


def _movement_direction(
    before: _escape_core.State,
    after: _escape_core.State,
) -> str | None:
    exit_direction = after.outcome["exit_direction"]
    if exit_direction is not None:
        return exit_direction
    before_row, before_col = before.ball
    after_row, after_col = after.ball
    delta = after_row - before_row, after_col - before_col
    return {(-1, 0): "up", (0, 1): "right", (1, 0): "down", (0, -1): "left"}.get(delta)


def _continues_direction(
    before: _escape_core.State,
    after: _escape_core.State,
    direction: str,
) -> bool:
    return _movement_direction(before, after) == direction


def transition_features(
    before: _escape_core.State,
    action: int,
    after: _escape_core.State,
    *,
    compute_reply_resistance: bool = False,
) -> TransitionFeatures:
    direction = _movement_direction(before, after)
    resistance: int | None = None
    if compute_reply_resistance and direction is not None and after.outcome["status"] == "playing":
        resistance = sum(
            not _continues_direction(after, after.apply(reply), direction)
            for reply in after.legal_actions()
        )
    return TransitionFeatures(
        move_kind=str(before.legal_move_kind(action)),
        new_walls=len(after.walls()) - len(before.walls()),
        ball_moved=direction is not None,
        ball_move_direction=direction,
        reply_resistance=resistance,
    )
