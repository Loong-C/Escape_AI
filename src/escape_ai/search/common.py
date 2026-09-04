"""Shared state evaluation helpers."""

from __future__ import annotations

from escape_ai import _escape_core


def terminal_value(state: _escape_core.State, perspective: str) -> float | None:
    status = state.outcome["status"]
    if status == "playing":
        return None
    if status == "draw":
        return 0.0
    return 1.0 if state.outcome["winner"] == perspective else -1.0


def _finite_distance(value: int, size: int) -> float:
    if value >= _escape_core.INFINITY_DISTANCE:
        return float(size * 3)
    return float(value)


def heuristic_value(state: _escape_core.State, perspective: str) -> float:
    terminal = terminal_value(state, perspective)
    if terminal is not None:
        return terminal * 1_000_000.0

    up, right, down, left = state.directional_exit_distances()
    horizontal = min(_finite_distance(left, state.size), _finite_distance(right, state.size))
    vertical = min(_finite_distance(up, state.size), _finite_distance(down, state.size))
    own_distance = horizontal if perspective == "white" else vertical
    opponent_distance = vertical if perspective == "white" else horizontal

    row, col = state.ball
    horizontal_progress = state.size / 2 - min(col + 1, state.size - col)
    vertical_progress = state.size / 2 - min(row + 1, state.size - row)
    axis_progress = (
        horizontal_progress - vertical_progress
        if perspective == "white"
        else vertical_progress - horizontal_progress
    )

    own_posts = sum(post == perspective for post in state.posts)
    opponent = "black" if perspective == "white" else "white"
    opponent_posts = sum(post == opponent for post in state.posts)
    own_walls = sum(wall[3] == perspective for wall in state.walls())
    opponent_walls = sum(wall[3] == opponent for wall in state.walls())
    own_anchors = sum(
        state.post(row_index, col_index) == perspective and state.is_anchored(row_index, col_index)
        for row_index in range(state.size + 1)
        for col_index in range(state.size + 1)
    )
    opponent_anchors = sum(
        state.post(row_index, col_index) == opponent and state.is_anchored(row_index, col_index)
        for row_index in range(state.size + 1)
        for col_index in range(state.size + 1)
    )

    return (
        12.0 * (opponent_distance - own_distance)
        + 3.0 * axis_progress
        + 1.5 * (own_walls - opponent_walls)
        + 0.4 * (own_anchors - opponent_anchors)
        + 0.1 * (own_posts - opponent_posts)
    )


def ordered_actions(
    state: _escape_core.State,
    perspective: str,
    maximum: int | None = None,
) -> list[int]:
    scored: list[tuple[float, int]] = []
    for action in state.legal_actions():
        child = state.apply(action)
        value = heuristic_value(child, perspective)
        if state.legal_move_kind(action) == "replace":
            value += 0.25
        scored.append((value, action))
    reverse = state.turn == perspective
    scored.sort(key=lambda item: (item[0], -item[1]), reverse=reverse)
    actions = [action for _, action in scored]
    return actions if maximum is None else actions[:maximum]
