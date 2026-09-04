from __future__ import annotations

from pathlib import Path

from escape_ai.research.data import write_research_shard
from escape_ai.research.games import ResearchSearchConfig, play_research_games
from escape_ai.research.viewer_api import ResearchGameRepository
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
