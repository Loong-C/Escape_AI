from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from escape_ai.research.games import ResearchSearchConfig
from escape_ai.research.runner import (
    _generate_side,
    _restore_summaries,
    load_research_run_config,
)
from escape_ai.search import D4SymmetryEnsembleEvaluator, UniformEvaluator


def test_committed_research_smoke_config_loads() -> None:
    config = load_research_run_config(Path("configs/games/research-smoke-3x3-v1.yaml"))
    assert config.games == 4
    assert config.search.simulations == 32
    assert config.search.compute_reply_resistance
    assert config.white == config.black
    assert config.white_evaluator.kind == "raw"
    assert config.starting_player_mode == "white"


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


def test_first_player_diagnostic_pairs_original_seeds_and_ensemble() -> None:
    config = load_research_run_config(
        Path("configs/games/champion-first-player-diagnostic-17x17-v1.yaml")
    )

    assert config.games == 2_000
    assert config.starting_player_mode == "paired"
    assert not config.paired_colors
    assert config.white_evaluator == config.black_evaluator
    assert config.white_evaluator.kind == "d4-ensemble"
    assert config.search.simulations == 512
    assert config.seed == 20260912


def test_research_runner_assigns_one_seed_to_paired_starting_players() -> None:
    formal = load_research_run_config(
        Path("configs/games/champion-first-player-diagnostic-17x17-v1.yaml")
    )
    config = replace(
        formal,
        games=2,
        games_per_shard=2,
        actor_batch_size=2,
        search=ResearchSearchConfig(
            board_size=3,
            simulations=4,
            parallel_leaves=2,
            opening_plies=2,
            opening_temperature=0.8,
        ),
    )
    evaluator = D4SymmetryEnsembleEvaluator(UniformEvaluator(), maximum_batch_size=64)

    games = _generate_side(
        [0, 1],
        config=config,
        white_evaluator=evaluator,
        black_evaluator=evaluator,
        white_id="uniform-d4",
        black_id="uniform-d4",
        pair_agent_seeds=False,
    )

    assert [game.seed for game in games] == [config.seed, config.seed]
    assert [game.moves[0].turn for game in games] == ["white", "black"]


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
