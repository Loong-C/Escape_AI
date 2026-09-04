from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from escape_ai import _escape_core
from escape_ai.research.data import write_research_shard
from escape_ai.research.features import position_features, transition_features
from escape_ai.research.games import ResearchSearchConfig, play_research_games
from escape_ai.search import UniformEvaluator


def test_position_and_transition_features_are_consistent() -> None:
    before = _escape_core.State(3)
    after = before.apply(0)
    features = position_features(before)
    transition = transition_features(before, 0, after)
    assert features.ball_row == 1
    assert features.ball_col == 1
    assert features.legal_actions == 16
    assert features.white_posts == features.black_posts == 0
    assert transition.move_kind == "place"
    assert transition.new_walls == 0


def test_research_games_write_queryable_parquet(tmp_path: Path) -> None:
    games = play_research_games(
        UniformEvaluator(),
        ResearchSearchConfig(board_size=3, simulations=8, parallel_leaves=4),
        seeds=[51, 52],
        white_model_id="uniform",
        game_ids=["research-a", "research-b"],
    )
    assert len(games) == 2
    assert all(game.moves for game in games)
    path = tmp_path / "research.parquet"
    summary = write_research_shard(path, games, metadata={"tier": "test"})
    assert summary.games == 2
    assert summary.moves == sum(len(game.moves) for game in games)
    table = pq.read_table(path)
    assert table.num_rows == summary.moves
    assert set(table.column_names) >= {
        "candidate_actions",
        "candidate_visits",
        "first_step_costs",
        "reply_resistance",
        "winner",
    }
