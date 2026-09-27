from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from escape_ai.play import PlayModelInfo, PlayService
from escape_ai.research.data import write_research_shard
from escape_ai.research.games import ResearchSearchConfig, play_research_games
from escape_ai.research.viewer_api import ResearchGameRepository, create_viewer_app
from escape_ai.search import UniformEvaluator


def test_viewer_repository_lists_and_decodes_games(tmp_path: Path) -> None:
    games = play_research_games(
        UniformEvaluator(),
        ResearchSearchConfig(board_size=3, simulations=4, parallel_leaves=2),
        seeds=[61],
        white_model_id="uniform",
        game_ids=["viewer-game"],
    )
    write_research_shard(tmp_path / "games.parquet", games)
    repository = ResearchGameRepository(tmp_path)
    summaries = repository.list_games()
    assert len(summaries) == 1
    assert summaries[0]["game_id"] == "viewer-game"
    game = repository.get_game("viewer-game")
    assert game is not None
    assert game["board_size"] == 3
    moves = game["moves"]
    assert isinstance(moves, list)
    assert moves
    assert len(moves[0]["state"]["posts"]) == 16
    assert game["final_state"]["outcome"]["status"] != "playing"
    assert repository.get_game("missing") is None


def test_viewer_play_api_runs_server_authoritative_round_trip(tmp_path: Path) -> None:
    games = play_research_games(
        UniformEvaluator(),
        ResearchSearchConfig(board_size=3, simulations=2, parallel_leaves=1),
        seeds=[73],
        white_model_id="uniform",
        game_ids=["api-fixture"],
    )
    write_research_shard(tmp_path / "games.parquet", games)
    play_service = PlayService(
        UniformEvaluator(),
        PlayModelInfo(
            name="api test",
            checkpoint_sha256="0" * 64,
            evaluator="uniform",
            board_size=3,
            simulations=2,
            c_puct=1.5,
            parallel_leaves=1,
            device="cpu",
        ),
    )
    client = TestClient(create_viewer_app(ResearchGameRepository(tmp_path), None, play_service))

    configuration = client.get("/api/play")
    assert configuration.status_code == 200
    assert configuration.json()["enabled"] is True

    created = client.post("/api/play/games", json={"human_player": "white"})
    assert created.status_code == 200
    payload = created.json()
    action = payload["legal_actions"][0]
    moved = client.post(
        f"/api/play/games/{payload['session_id']}/moves",
        json={"action": action},
    )
    assert moved.status_code == 200
    assert [move["actor"] for move in moved.json()["moves"]] == ["human", "ai"]

    illegal = client.post(
        f"/api/play/games/{payload['session_id']}/moves",
        json={"action": -1},
    )
    assert illegal.status_code == 409
