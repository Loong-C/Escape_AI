"""Reproducible, storage-safe single-generation training experiments."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch
import yaml  # type: ignore[import-untyped]

from escape_ai.paths import ensure_artifact_layout, require_artifact_capacity
from escape_ai.search import TorchEvaluator

from .checkpoint import CheckpointSummary, save_checkpoint
from .data import ShardSummary, load_training_batch, sha256_file, write_training_shard
from .learner import LearnerConfig, LearnerMetrics, train_model
from .model import NetworkConfig, PolicyValueNet
from .selfplay import SelfPlayConfig, SelfPlayGame, play_self_games

EXPERIMENT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    experiment_id: str
    lineage: str
    seed: int
    games: int
    games_per_shard: int
    device: str
    network: NetworkConfig
    self_play: SelfPlayConfig
    learner: LearnerConfig
    self_play_batch_size: int = 1
    require_clean_worktree: bool = True


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    experiment_id: str
    git_commit: str
    games: int
    positions: int
    elapsed_seconds: float
    shards: tuple[ShardSummary, ...]
    learner: LearnerMetrics
    checkpoint: CheckpointSummary
    manifest: Path


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def load_experiment_config(path: Path) -> ExperimentConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    root = _mapping(raw, "experiment")
    if root.get("schema_version") != EXPERIMENT_SCHEMA_VERSION:
        raise ValueError("unsupported experiment schema version")
    network = NetworkConfig(**dict(_mapping(root["network"], "network")))
    self_play = SelfPlayConfig(**dict(_mapping(root["self_play"], "self_play")))
    learner = LearnerConfig(**dict(_mapping(root["learner"], "learner")))
    games = int(root["games"])
    games_per_shard = int(root["games_per_shard"])
    if games < 1 or games_per_shard < 1:
        raise ValueError("games and games_per_shard must be positive")
    self_play_batch_size = int(root.get("self_play_batch_size", 1))
    if self_play_batch_size < 1:
        raise ValueError("self_play_batch_size must be positive")
    return ExperimentConfig(
        experiment_id=str(root["experiment_id"]),
        lineage=str(root["lineage"]),
        seed=int(root["seed"]),
        games=games,
        games_per_shard=games_per_shard,
        device=str(root.get("device", "cuda")),
        network=network,
        self_play=self_play,
        learner=learner,
        self_play_batch_size=self_play_batch_size,
        require_clean_worktree=bool(root.get("require_clean_worktree", True)),
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


def _hardware() -> dict[str, object]:
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


def _ensure_new_experiment(paths: Mapping[str, Path], experiment_id: str) -> None:
    candidates = (
        paths["runs"] / experiment_id,
        paths["replay"] / experiment_id,
        paths["checkpoints"] / experiment_id,
    )
    if any(path.exists() and any(path.iterdir()) for path in candidates):
        raise FileExistsError(f"experiment {experiment_id!r} already has artifacts")


def run_experiment(
    config_path: Path,
    *,
    repo_root: Path,
    progress: Callable[[str], None] | None = None,
) -> ExperimentResult:
    """Run self-play, one learner phase, and a provenance-complete checkpoint."""

    emit = progress or (lambda _message: None)
    config = load_experiment_config(config_path)
    git_commit = _git(repo_root, "rev-parse", "HEAD")
    if config.require_clean_worktree and _git(repo_root, "status", "--porcelain"):
        raise RuntimeError("formal experiments require a clean Git worktree")
    paths = ensure_artifact_layout()
    _ensure_new_experiment(paths, config.experiment_id)
    require_artifact_capacity(paths["root"], expected_new_bytes=1024**3)
    config_hash = sha256_file(config_path)

    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)
    model = PolicyValueNet(config.network)
    evaluator = TorchEvaluator(model, config.device)
    started = time.perf_counter()
    shards: list[ShardSummary] = []
    buffered: list[SelfPlayGame] = []

    def write_buffered(games_to_write: list[SelfPlayGame]) -> None:
        shard_index = len(shards)
        shard_path = paths["replay"] / config.experiment_id / f"shard-{shard_index:05d}.parquet"
        shards.append(
            write_training_shard(
                shard_path,
                games_to_write,
                metadata={
                    "experiment_id": config.experiment_id,
                    "git_commit": git_commit,
                    "config_sha256": config_hash,
                },
            )
        )

    completed_games = 0
    while completed_games < config.games:
        wave_size = min(config.self_play_batch_size, config.games - completed_games)
        indices = list(range(completed_games, completed_games + wave_size))
        buffered.extend(
            play_self_games(
                evaluator,
                config.self_play,
                seeds=[config.seed + index for index in indices],
                model_id=f"{config.experiment_id}-initial",
                game_ids=[f"{config.experiment_id}-{index:08d}" for index in indices],
            )
        )
        completed_games += wave_size
        emit(f"self-play {completed_games}/{config.games}")
        while len(buffered) >= config.games_per_shard:
            games_to_write = buffered[: config.games_per_shard]
            del buffered[: config.games_per_shard]
            write_buffered(games_to_write)
    if buffered:
        write_buffered(buffered)

    training_batch = load_training_batch(shard.path for shard in shards)
    optimizer, learner_metrics = train_model(
        model,
        training_batch,
        config.learner,
        device=config.device,
        seed=config.seed,
    )
    checkpoint_path = paths["checkpoints"] / config.experiment_id / "final.pt"
    checkpoint = save_checkpoint(
        checkpoint_path,
        model,
        optimizer=optimizer,
        metadata={
            "experiment_id": config.experiment_id,
            "lineage": config.lineage,
            "seed": config.seed,
            "git_commit": git_commit,
            "config_sha256": config_hash,
            "data_sha256": [shard.sha256 for shard in shards],
        },
    )
    elapsed = time.perf_counter() - started
    positions = sum(shard.positions for shard in shards)
    manifest_path = paths["runs"] / config.experiment_id / "manifest.json"
    _atomic_json(
        manifest_path,
        {
            "schema_version": EXPERIMENT_SCHEMA_VERSION,
            "experiment": asdict(config),
            "config_path": str(config_path.resolve()),
            "config_sha256": config_hash,
            "git_commit": git_commit,
            "hardware": _hardware(),
            "games": config.games,
            "positions": positions,
            "elapsed_seconds": elapsed,
            "shards": [{**asdict(shard), "path": str(shard.path)} for shard in shards],
            "learner": asdict(learner_metrics),
            "checkpoint": {**asdict(checkpoint), "path": str(checkpoint.path)},
        },
    )
    return ExperimentResult(
        config.experiment_id,
        git_commit,
        config.games,
        positions,
        elapsed,
        tuple(shards),
        learner_metrics,
        checkpoint,
        manifest_path,
    )
