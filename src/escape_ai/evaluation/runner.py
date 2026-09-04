"""Configuration-driven checkpoint league runner."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from escape_ai.paths import ensure_artifact_layout, require_artifact_capacity
from escape_ai.search import (
    GreedyAgent,
    HeuristicAgent,
    PureMCTSAgent,
    RandomAgent,
    TorchEvaluator,
)
from escape_ai.search.agents import Agent
from escape_ai.search.neural_agent import NeuralPUCTAgent
from escape_ai.training.checkpoint import load_checkpoint
from escape_ai.training.data import sha256_file

from .league import LeagueEntry, LeagueResult, run_league

LEAGUE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class CheckpointLeagueConfig:
    league_id: str
    seed: int
    board_size: int
    games_per_matchup: int
    simulations: int
    c_puct: float
    device: str
    checkpoint: Path
    checkpoint_sha256: str
    opponents: tuple[str, ...]
    pure_mcts_simulations: int
    require_clean_worktree: bool = True


@dataclass(frozen=True, slots=True)
class CheckpointLeagueResult:
    config: CheckpointLeagueConfig
    git_commit: str
    model_id: str
    league: LeagueResult
    output: Path


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def load_league_config(path: Path) -> CheckpointLeagueConfig:
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "league")
    if raw.get("schema_version") != LEAGUE_SCHEMA_VERSION:
        raise ValueError("unsupported league configuration schema")
    checkpoint = _mapping(raw["checkpoint"], "checkpoint")
    return CheckpointLeagueConfig(
        league_id=str(raw["league_id"]),
        seed=int(raw["seed"]),
        board_size=int(raw["board_size"]),
        games_per_matchup=int(raw["games_per_matchup"]),
        simulations=int(raw["simulations"]),
        c_puct=float(raw.get("c_puct", 1.5)),
        device=str(raw.get("device", "cuda")),
        checkpoint=Path(str(checkpoint["path"])),
        checkpoint_sha256=str(checkpoint["sha256"]),
        opponents=tuple(str(value) for value in raw["opponents"]),
        pure_mcts_simulations=int(raw.get("pure_mcts_simulations", 100)),
        require_clean_worktree=bool(raw.get("require_clean_worktree", True)),
    )


def _git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _opponent(name: str, pure_mcts_simulations: int) -> Agent:
    agents: dict[str, Agent] = {
        "random": RandomAgent(),
        "greedy": GreedyAgent(),
        "heuristic": HeuristicAgent(),
        "pure-mcts": PureMCTSAgent(simulations=pure_mcts_simulations),
    }
    try:
        return agents[name]
    except KeyError as error:
        raise ValueError(f"unknown fixed opponent {name!r}") from error


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_checkpoint_league(
    config_path: Path,
    *,
    repo_root: Path,
) -> CheckpointLeagueResult:
    config = load_league_config(config_path)
    git_commit = _git(repo_root, "rev-parse", "HEAD")
    if config.require_clean_worktree and _git(repo_root, "status", "--porcelain"):
        raise RuntimeError("formal leagues require a clean Git worktree")
    actual_hash = sha256_file(config.checkpoint)
    if actual_hash != config.checkpoint_sha256:
        raise ValueError("checkpoint SHA-256 does not match league configuration")
    paths = ensure_artifact_layout()
    require_artifact_capacity(paths["root"], expected_new_bytes=128 * 1024**2)
    output = paths["runs"] / config.league_id / "league.json"
    if output.exists():
        raise FileExistsError(f"league {config.league_id!r} already exists")

    model, _metadata = load_checkpoint(config.checkpoint, device=config.device)
    model_id = actual_hash[:16]
    model_agent = NeuralPUCTAgent(
        TorchEvaluator(model, config.device),
        simulations=config.simulations,
        model_id=model_id,
        c_puct=config.c_puct,
    )
    entries = [LeagueEntry(model_agent.name, model_agent)]
    entries.extend(
        LeagueEntry(name, _opponent(name, config.pure_mcts_simulations))
        for name in config.opponents
    )
    league = run_league(
        entries,
        games_per_matchup=config.games_per_matchup,
        board_size=config.board_size,
        seed=config.seed,
    )
    _atomic_json(
        output,
        {
            "schema_version": LEAGUE_SCHEMA_VERSION,
            "league_id": config.league_id,
            "git_commit": git_commit,
            "config_path": str(config_path.resolve()),
            "config_sha256": sha256_file(config_path),
            "checkpoint_sha256": actual_hash,
            "model_id": model_id,
            "settings": {
                **asdict(config),
                "checkpoint": str(config.checkpoint),
            },
            "league": asdict(league),
        },
    )
    return CheckpointLeagueResult(config, git_commit, model_id, league, output)
