from __future__ import annotations

from pathlib import Path

from escape_ai.research.runner import load_research_run_config


def test_committed_research_smoke_config_loads() -> None:
    config = load_research_run_config(Path("configs/games/research-smoke-3x3-v1.yaml"))
    assert config.games == 4
    assert config.search.simulations == 32
    assert config.search.compute_reply_resistance
    assert config.white == config.black
