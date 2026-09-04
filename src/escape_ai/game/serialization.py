"""Versioned canonical state serialization for fixtures and engine exchange."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .types import Cell, Direction, GameState, Outcome, OutcomeStatus, Player, WinReason

SCHEMA_VERSION = 1


def state_to_dict(state: GameState) -> dict[str, Any]:
    posts = "".join(
        "." if post is None else "W" if post is Player.WHITE else "B" for post in state.posts
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "size": state.size,
        "posts": posts,
        "ball": {"row": state.ball.row, "col": state.ball.col},
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


def _required_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _required_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def state_from_dict(payload: Mapping[str, object]) -> GameState:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported state schema version")
    size = _required_int(payload["size"], "size")
    raw_posts = payload["posts"]
    if not isinstance(raw_posts, str) or len(raw_posts) != (size + 1) ** 2:
        raise ValueError("invalid encoded post array")
    post_codes = {".": None, "W": Player.WHITE, "B": Player.BLACK}
    try:
        posts = tuple(post_codes[code] for code in raw_posts)
    except KeyError as error:
        raise ValueError("invalid post code") from error

    raw_ball = _required_mapping(payload["ball"], "ball")
    raw_outcome = _required_mapping(payload["outcome"], "outcome")
    status = OutcomeStatus(str(raw_outcome["status"]))
    winner_value = raw_outcome.get("winner")
    reason_value = raw_outcome.get("reason")
    exit_value = raw_outcome.get("exit_direction")
    outcome = Outcome(
        status=status,
        winner=Player(str(winner_value)) if winner_value is not None else None,
        reason=WinReason(str(reason_value)) if reason_value is not None else None,
        exit_direction=Direction(str(exit_value)) if exit_value is not None else None,
    )
    return GameState(
        size=size,
        posts=posts,
        ball=Cell(
            _required_int(raw_ball["row"], "ball.row"),
            _required_int(raw_ball["col"], "ball.col"),
        ),
        turn=Player(str(payload["turn"])),
        ply=_required_int(payload["ply"], "ply"),
        outcome=outcome,
        last_move=None,
    )


def serialize_state(state: GameState) -> str:
    return json.dumps(
        state_to_dict(state), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def deserialize_state(serialized: str) -> GameState:
    payload = json.loads(serialized)
    if not isinstance(payload, dict):
        raise ValueError("state payload must be an object")
    return state_from_dict(payload)
