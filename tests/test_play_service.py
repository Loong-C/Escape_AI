from __future__ import annotations

import pytest

from escape_ai.play import (
    IllegalHumanMoveError,
    PlayModelInfo,
    PlayService,
    PlaySessionNotFoundError,
)
from escape_ai.search import UniformEvaluator


def _service(*, maximum_sessions: int = 64) -> PlayService:
    return PlayService(
        UniformEvaluator(),
        PlayModelInfo(
            name="test agent",
            checkpoint_sha256="0" * 64,
            evaluator="uniform",
            board_size=3,
            simulations=4,
            c_puct=1.5,
            parallel_leaves=2,
            device="cpu",
        ),
        maximum_sessions=maximum_sessions,
    )


def test_human_white_move_is_validated_and_gets_ai_reply() -> None:
    service = _service()
    created = service.create_game("white")
    assert created["human_player"] == "white"
    assert created["moves"] == []
    legal_actions = created["legal_actions"]
    assert isinstance(legal_actions, list)
    assert legal_actions

    updated = service.play_human_action(str(created["session_id"]), legal_actions[0])
    moves = updated["moves"]
    assert isinstance(moves, list)
    assert [move["actor"] for move in moves] == ["human", "ai"]
    assert updated["state"]["turn"] == "white"
    assert updated["legal_actions"]
    assert moves[-1]["candidates"]


def test_human_black_game_searches_opening_before_returning() -> None:
    created = _service().create_game("black")
    moves = created["moves"]
    assert isinstance(moves, list)
    assert len(moves) == 1
    assert moves[0]["actor"] == "ai"
    assert moves[0]["player"] == "white"
    assert created["state"]["turn"] == "black"
    assert created["legal_actions"]


def test_illegal_action_and_unknown_session_are_rejected() -> None:
    service = _service()
    created = service.create_game("white")
    with pytest.raises(IllegalHumanMoveError, match="not legal"):
        service.play_human_action(str(created["session_id"]), -1)
    with pytest.raises(PlaySessionNotFoundError):
        service.get_game("missing")


def test_oldest_session_is_evicted_at_capacity() -> None:
    service = _service(maximum_sessions=1)
    first = service.create_game("white")
    second = service.create_game("white")
    with pytest.raises(PlaySessionNotFoundError):
        service.get_game(str(first["session_id"]))
    assert service.get_game(str(second["session_id"]))["session_id"] == second["session_id"]
