"""Typed access and normalization helpers for the C++ rules core."""

from __future__ import annotations

from math import inf
from typing import Any

from escape_ai import _escape_core

from .types import GameState, Symmetry

SYMMETRY_TO_CORE = {
    Symmetry.IDENTITY: _escape_core.Symmetry.IDENTITY,
    Symmetry.ROTATE_90: _escape_core.Symmetry.ROTATE_90,
    Symmetry.ROTATE_180: _escape_core.Symmetry.ROTATE_180,
    Symmetry.ROTATE_270: _escape_core.Symmetry.ROTATE_270,
    Symmetry.FLIP_HORIZONTAL: _escape_core.Symmetry.FLIP_HORIZONTAL,
    Symmetry.FLIP_VERTICAL: _escape_core.Symmetry.FLIP_VERTICAL,
    Symmetry.DIAGONAL_MAIN: _escape_core.Symmetry.DIAGONAL_MAIN,
    Symmetry.DIAGONAL_ANTI: _escape_core.Symmetry.DIAGONAL_ANTI,
}


def create_core_state(size: int = 17) -> _escape_core.State:
    return _escape_core.State(size)


def _distance(value: int) -> float:
    return inf if value >= _escape_core.INFINITY_DISTANCE else float(value)


def reference_snapshot(state: GameState) -> dict[str, Any]:
    return {
        "size": state.size,
        "posts": [post.value if post is not None else None for post in state.posts],
        "ball": (state.ball.row, state.ball.col),
        "turn": state.turn.value,
        "ply": state.ply,
        "outcome": {
            "status": state.outcome.status.value,
            "winner": state.outcome.winner.value if state.outcome.winner else None,
            "reason": state.outcome.reason.value if state.outcome.reason else None,
            "exit_direction": (
                state.outcome.exit_direction.value
                if state.outcome.exit_direction is not None
                else None
            ),
        },
    }


def core_snapshot(state: _escape_core.State) -> dict[str, Any]:
    return {
        "size": state.size,
        "posts": state.posts,
        "ball": state.ball,
        "turn": state.turn,
        "ply": state.ply,
        "outcome": state.outcome,
    }


def core_costs(state: _escape_core.State) -> tuple[float, float, float, float]:
    up, right, down, left = state.first_step_costs()
    return (_distance(up), _distance(right), _distance(down), _distance(left))


def core_exit_distances(state: _escape_core.State) -> tuple[float, float, float, float]:
    up, right, down, left = state.directional_exit_distances()
    return (_distance(up), _distance(right), _distance(down), _distance(left))
