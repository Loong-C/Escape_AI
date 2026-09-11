from __future__ import annotations

from pathlib import Path

from escape_ai.research.runner import load_research_run_config


def test_committed_research_smoke_config_loads() -> None:
    config = load_research_run_config(Path("configs/games/research-smoke-3x3-v1.yaml"))
    assert config.games == 4
    assert config.search.simulations == 32
    assert config.search.compute_reply_resistance
    assert config.white == config.black


def test_committed_champion_analysis_locks_formal_budget_and_checkpoint() -> None:
    config = load_research_run_config(
        Path("configs/games/champion-analysis-17x17-v1.yaml")
    )

    assert config.games == 1_000
    assert config.games_per_shard == 20
    assert config.search.board_size == 17
    assert config.search.simulations == 512
    assert config.search.opening_plies == 20
    assert config.search.compute_reply_resistance
    assert config.white == config.black
    assert config.white.sha256 == (
        "0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3"
    )
