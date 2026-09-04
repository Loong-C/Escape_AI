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
