from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from escape_ai import _escape_core
from escape_ai.search import UniformEvaluator
from escape_ai.training.data import load_training_batch, write_training_shard
from escape_ai.training.selfplay import SelfPlayConfig, play_self_game, play_self_games


def deterministic_id() -> str:
    return "test-game"


def test_self_play_labels_and_reproduces() -> None:
    config = SelfPlayConfig(board_size=3, simulations=8, temperature_drop_ply=4)
    first = play_self_game(
        UniformEvaluator(),
        config,
        seed=19,
        model_id="uniform",
        game_id_factory=deterministic_id,
    )
    second = play_self_game(
        UniformEvaluator(),
        config,
        seed=19,
        model_id="uniform",
        game_id_factory=deterministic_id,
    )
    assert first.game_id == second.game_id
    assert first.winner == second.winner
    assert [position.action for position in first.positions] == [
        position.action for position in second.positions
    ]
    assert 0 < first.plies <= 2 * 4**2
    for position in first.positions:
        assert position.policy.sum() == pytest.approx(1.0)
        expected = 0.0 if first.winner is None else 1.0 if first.winner == position.turn else -1.0
        assert position.value_target == expected


def test_batched_self_play_preserves_game_order_and_seeds() -> None:
    games = play_self_games(
        UniformEvaluator(),
        SelfPlayConfig(board_size=3, simulations=4),
        seeds=[101, 102, 103],
        model_id="uniform",
        game_ids=["a", "b", "c"],
    )
    assert [game.game_id for game in games] == ["a", "b", "c"]
    assert [game.seed for game in games] == [101, 102, 103]
    assert all(game.plies > 0 for game in games)


def test_parquet_shard_round_trips_into_training_arrays(tmp_path: Path) -> None:
    game = play_self_game(
        UniformEvaluator(),
        SelfPlayConfig(board_size=3, simulations=4),
        seed=23,
        model_id="uniform",
        game_id_factory=deterministic_id,
    )
    path = tmp_path / "replay.parquet"
    summary = write_training_shard(path, [game], metadata={"git_commit": "test"})
    assert summary.games == 1
    assert summary.positions == game.plies
    assert summary.bytes > 0
    assert len(summary.sha256) == 64
    table = pq.read_table(path)
    assert table.schema.metadata is not None
    assert table.num_rows == game.plies

    batch = load_training_batch([path])
    assert batch.features.shape == (game.plies, 6, 4, 4)
    assert batch.policies.shape == (game.plies, 16)
    assert batch.legal_masks.shape == (game.plies, 16)
    assert batch.values.shape == (game.plies,)
    for row, serialized in enumerate(table.column("state").to_pylist()):
        state = _escape_core.State.deserialize(serialized)
        assert np.flatnonzero(batch.legal_masks[row]).tolist() == state.legal_actions()
