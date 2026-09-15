from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from escape_ai import _escape_core
from escape_ai.search import UniformEvaluator
from escape_ai.training.data import (
    TRAINING_D4_SYMMETRIES,
    canonicalize_training_position,
    load_training_batch,
    load_training_sample,
    transform_training_position,
    write_training_shard,
)
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

    sample = load_training_sample([path], maximum_positions=5, seed=77)
    repeated = load_training_sample([path], maximum_positions=5, seed=77)
    assert sample.features.shape[0] == 5
    np.testing.assert_array_equal(sample.features, repeated.features)

    augmented = load_training_sample(
        [path],
        maximum_positions=5,
        seed=77,
        symmetry_augmentation="random-d4",
    )
    repeated_augmented = load_training_sample(
        [path],
        maximum_positions=5,
        seed=77,
        symmetry_augmentation="random-d4",
    )
    np.testing.assert_array_equal(augmented.features, repeated_augmented.features)
    np.testing.assert_array_equal(augmented.policies, repeated_augmented.policies)
    assert np.all(augmented.policies[~augmented.legal_masks] == 0.0)
    np.testing.assert_allclose(augmented.policies.sum(axis=1), 1.0)


def test_role_aware_training_augmentation_maps_every_d4_policy() -> None:
    state = _escape_core.State(3)
    state = state.apply(0)
    state = state.apply(5)
    legal = state.legal_actions()
    policy = np.zeros(16, dtype=np.float32)
    policy[legal] = np.arange(1, len(legal) + 1, dtype=np.float32)
    policy /= policy.sum()

    for symmetry in TRAINING_D4_SYMMETRIES:
        transformed, transformed_policy = transform_training_position(
            state, policy, symmetry
        )
        expected = state.transformed(symmetry)
        assert transformed.serialize() == expected.serialize()
        expected_legal = sorted(
            _escape_core.transform_action(action, state.size, symmetry)
            for action in legal
        )
        assert transformed.legal_actions() == expected_legal
        for action in range(16):
            target = _escape_core.transform_action(action, state.size, symmetry)
            assert transformed_policy[target] == policy[action]


def test_canonical_training_target_is_independent_of_source_orientation() -> None:
    state = _escape_core.State(3).apply(0).apply(5)
    legal = state.legal_actions()
    policy = np.zeros(16, dtype=np.float32)
    policy[legal] = np.arange(1, len(legal) + 1, dtype=np.float32)
    policy /= policy.sum()
    expected_state, expected_policy = canonicalize_training_position(state, policy)

    for symmetry in TRAINING_D4_SYMMETRIES:
        transformed_state, transformed_policy = transform_training_position(
            state, policy, symmetry
        )
        actual_state, actual_policy = canonicalize_training_position(
            transformed_state, transformed_policy
        )
        assert actual_state.serialize() == expected_state.serialize()
        np.testing.assert_allclose(actual_policy, expected_policy, atol=1e-8)


def test_canonical_training_target_averages_a_symmetric_state_stabilizer() -> None:
    state = _escape_core.State(3)
    legal = state.legal_actions()
    policy = np.zeros(16, dtype=np.float32)
    policy[legal] = np.arange(1, len(legal) + 1, dtype=np.float32)
    policy /= policy.sum()

    canonical, canonical_policy = canonicalize_training_position(state, policy)

    assert canonical.serialize() == state.serialize()
    for symmetry in TRAINING_D4_SYMMETRIES:
        _, transformed_policy = transform_training_position(
            canonical, canonical_policy, symmetry
        )
        np.testing.assert_allclose(transformed_policy, canonical_policy, atol=1e-8)
    np.testing.assert_allclose(canonical_policy.sum(), 1.0)
