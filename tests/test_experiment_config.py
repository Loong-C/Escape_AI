from __future__ import annotations

from pathlib import Path

import pytest

from escape_ai.paths import require_artifact_capacity
from escape_ai.training.experiment import load_experiment_config


def test_committed_smoke_experiment_loads() -> None:
    config = load_experiment_config(Path("configs/experiments/az-smoke-3x3.yaml"))
    assert config.experiment_id == "az-smoke-3x3-v1"
    assert config.self_play.board_size == 3
    assert config.self_play.simulations == 32
    assert config.network.residual_blocks == 3
    assert config.learner.steps == 20


def test_storage_guard_rejects_impossible_request(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="artifact budget"):
        require_artifact_capacity(tmp_path, expected_new_bytes=2, maximum_bytes=1)
