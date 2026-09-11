from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from escape_ai.research.runner import _restore_summaries, load_research_run_config


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


def test_restore_summaries_validates_recorded_size_and_hash(tmp_path: Path) -> None:
    shard = tmp_path / "shard.parquet"
    shard.write_bytes(b"recorded research shard")
    digest = hashlib.sha256(shard.read_bytes()).hexdigest()
    recorded = [
        {
            "path": str(shard),
            "games": 2,
            "moves": 17,
            "bytes": shard.stat().st_size,
            "sha256": digest,
        }
    ]

    summaries = _restore_summaries(recorded)
    assert summaries[0].sha256 == digest

    shard.write_bytes(b"tampered research shard with extra bytes")
    with pytest.raises(RuntimeError, match="research shard size mismatch"):
        _restore_summaries(recorded)

    recorded[0]["bytes"] = shard.stat().st_size
    with pytest.raises(RuntimeError, match="research shard hash mismatch"):
        _restore_summaries(recorded)
