from __future__ import annotations

from pathlib import Path

import pytest

from escape_ai.training.lineage import load_lineage_config


@pytest.mark.parametrize("lineage", ["a", "b", "c"])
def test_production_lineages_each_target_one_hundred_thousand_games(lineage: str) -> None:
    config = load_lineage_config(Path(f"configs/lineages/lineage-{lineage}-17x17-v1.yaml"))
    assert config.self_play.board_size == 17
    assert config.total_games == 100_000
    assert config.seed in {20260903, 20260904, 20260905}
    assert config.self_play.parallel_leaves == 16


def test_lineage_smoke_config_has_two_generations() -> None:
    config = load_lineage_config(Path("configs/lineages/smoke-3x3-v1.yaml"))
    assert config.generations == 2
    assert config.total_games == 8


def test_d4_smoke_lineage_uses_role_aware_augmentation() -> None:
    config = load_lineage_config(Path("configs/lineages/d4-smoke-3x3-v1.yaml"))
    assert config.total_games == 8
    assert config.learner.symmetry_augmentation == "random-d4"
    assert config.initial_checkpoint is None


def test_d4_finetune_lineage_locks_champion_and_repair_budget() -> None:
    config = load_lineage_config(
        Path("configs/lineages/lineage-c-d4-finetune-17x17-v1.yaml")
    )
    assert config.total_games == 50_000
    assert config.learner.learning_rate == 0.0005
    assert config.learner.symmetry_augmentation == "random-d4"
    assert config.initial_checkpoint is not None
    assert not config.initial_checkpoint.inherit_optimizer
    assert config.initial_checkpoint.sha256 == (
        "0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3"
    )


def test_d4_native_lineage_uses_full_from_scratch_budget() -> None:
    config = load_lineage_config(
        Path("configs/lineages/lineage-d-d4-native-17x17-v1.yaml")
    )
    assert config.total_games == 100_000
    assert config.learner.learning_rate == 0.002
    assert config.learner.symmetry_augmentation == "random-d4"
    assert config.initial_checkpoint is None


def test_canonical_d4_smoke_aligns_self_play_and_training_coordinates() -> None:
    config = load_lineage_config(
        Path("configs/lineages/canonical-d4-smoke-3x3-v1.yaml")
    )
    assert config.total_games == 8
    assert config.self_play_evaluator == "canonical-d4"
    assert config.learner.symmetry_augmentation == "canonical-d4"


def test_canonical_d4_native_lineage_preserves_full_control_budget() -> None:
    config = load_lineage_config(
        Path("configs/lineages/lineage-d-d4-canonical-17x17-v2.yaml")
    )
    control = load_lineage_config(Path("configs/lineages/lineage-c-17x17-v1.yaml"))
    assert config.total_games == control.total_games == 100_000
    assert config.network == control.network
    assert config.self_play == control.self_play
    assert config.learner.steps == control.learner.steps
    assert config.learner.learning_rate == control.learner.learning_rate
    assert config.self_play_evaluator == "canonical-d4"
    assert config.learner.symmetry_augmentation == "canonical-d4"
    assert config.initial_checkpoint is None
