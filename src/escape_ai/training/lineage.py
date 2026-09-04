"""Resumable multi-generation AlphaZero lineage training."""

from __future__ import annotations

import json
import os
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

from .checkpoint import (
    CheckpointSummary,
    load_training_checkpoint,
    save_checkpoint,
)
from .data import (
    ShardSummary,
    load_training_sample,
    sha256_file,
    write_training_shard,
)
from .learner import LearnerConfig, train_model
from .model import NetworkConfig, PolicyValueNet
from .selfplay import SelfPlayConfig, SelfPlayGame, play_self_games

LINEAGE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class LineageConfig:
    run_id: str
    lineage: str
    seed: int
    generations: int
    games_per_generation: int
    games_per_shard: int
    actor_batch_size: int
    replay_window_shards: int
    replay_sample_positions: int
    device: str
    network: NetworkConfig
    self_play: SelfPlayConfig
    learner: LearnerConfig
    require_clean_worktree: bool = True

    @property
    def total_games(self) -> int:
        return self.generations * self.games_per_generation


@dataclass(frozen=True, slots=True)
class LineageResult:
    run_id: str
    git_commit: str
    completed_generations: int
    total_games: int
    checkpoint: Path
    checkpoint_sha256: str
    progress_path: Path
    elapsed_seconds: float


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def load_lineage_config(path: Path) -> LineageConfig:
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "lineage")
    if raw.get("schema_version") != LINEAGE_SCHEMA_VERSION:
        raise ValueError("unsupported lineage configuration schema")
    config = LineageConfig(
        run_id=str(raw["run_id"]),
        lineage=str(raw["lineage"]),
        seed=int(raw["seed"]),
        generations=int(raw["generations"]),
        games_per_generation=int(raw["games_per_generation"]),
        games_per_shard=int(raw["games_per_shard"]),
        actor_batch_size=int(raw["actor_batch_size"]),
        replay_window_shards=int(raw["replay_window_shards"]),
        replay_sample_positions=int(raw["replay_sample_positions"]),
        device=str(raw.get("device", "cuda")),
        network=NetworkConfig(**dict(_mapping(raw["network"], "network"))),
        self_play=SelfPlayConfig(**dict(_mapping(raw["self_play"], "self_play"))),
        learner=LearnerConfig(**dict(_mapping(raw["learner"], "learner"))),
        require_clean_worktree=bool(raw.get("require_clean_worktree", True)),
    )
    positive = (
        config.generations,
        config.games_per_generation,
        config.games_per_shard,
        config.actor_batch_size,
        config.replay_window_shards,
        config.replay_sample_positions,
    )
    if any(value < 1 for value in positive):
        raise ValueError("lineage counts and sizes must be positive")
    if config.games_per_generation % config.games_per_shard != 0:
        raise ValueError("games_per_generation must be divisible by games_per_shard")
    return config


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


def _restore_shards(raw: object) -> list[ShardSummary]:
    if not isinstance(raw, list):
        raise ValueError("invalid lineage shard progress")
    summaries: list[ShardSummary] = []
    for value in raw:
        item = _mapping(value, "shard progress")
        summary = ShardSummary(
            path=Path(str(item["path"])),
            games=int(item["games"]),
            positions=int(item["positions"]),
            bytes=int(item["bytes"]),
            sha256=str(item["sha256"]),
        )
        if not summary.path.is_file():
            raise FileNotFoundError(summary.path)
        summaries.append(summary)
    return summaries


def _progress_payload(
    *,
    config: LineageConfig,
    config_path: Path,
    config_hash: str,
    git_commit: str,
    completed_generations: int,
    active_generation: int | None,
    active_games: int,
    shards: list[ShardSummary],
    checkpoints: list[CheckpointSummary],
    generation_metrics: list[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": LINEAGE_SCHEMA_VERSION,
        "run_id": config.run_id,
        "lineage": config.lineage,
        "config_path": str(config_path.resolve()),
        "config_sha256": config_hash,
        "git_commit": git_commit,
        "target_generations": config.generations,
        "target_games": config.total_games,
        "completed_generations": completed_generations,
        "active_generation": active_generation,
        "active_games": active_games,
        "shards": [{**asdict(item), "path": str(item.path)} for item in shards],
        "checkpoints": [{**asdict(item), "path": str(item.path)} for item in checkpoints],
        "generation_metrics": generation_metrics,
    }


def _make_optimizer(
    model: PolicyValueNet,
    config: LearnerConfig,
    state: dict[str, Any] | None,
) -> torch.optim.Optimizer | None:
    if state is None:
        return None
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    optimizer.load_state_dict(state)
    return optimizer


def run_lineage(
    config_path: Path,
    *,
    repo_root: Path,
    progress: Callable[[str], None] | None = None,
) -> LineageResult:
    """Run or resume one immutable-config lineage at shard boundaries."""

    emit = progress or (lambda _message: None)
    config = load_lineage_config(config_path)
    config_hash = sha256_file(config_path)
    git_commit = _git(repo_root, "rev-parse", "HEAD")
    if config.require_clean_worktree and _git(repo_root, "status", "--porcelain"):
        raise RuntimeError("formal lineages require a clean Git worktree")
    paths = ensure_artifact_layout()
    run_path = paths["runs"] / config.run_id
    replay_path = paths["replay"] / config.run_id
    checkpoint_path = paths["checkpoints"] / config.run_id
    progress_path = run_path / "progress.json"

    completed_generations = 0
    active_generation: int | None = None
    active_games = 0
    shards: list[ShardSummary] = []
    checkpoints: list[CheckpointSummary] = []
    generation_metrics: list[Mapping[str, object]] = []
    optimizer: torch.optim.Optimizer | None = None
    if progress_path.exists():
        saved = _mapping(json.loads(progress_path.read_text(encoding="utf-8")), "progress")
        if saved.get("config_sha256") != config_hash or saved.get("git_commit") != git_commit:
            raise RuntimeError("cannot resume lineage with different config or Git commit")
        completed_generations = int(saved["completed_generations"])
        active_raw = saved.get("active_generation")
        active_generation = int(active_raw) if active_raw is not None else None
        active_games = int(saved.get("active_games", 0))
        shards = _restore_shards(saved.get("shards", []))
        checkpoint_values = saved.get("checkpoints", [])
        if not isinstance(checkpoint_values, list):
            raise ValueError("invalid lineage checkpoint progress")
        checkpoints = [
            CheckpointSummary(
                Path(str(_mapping(value, "checkpoint")["path"])),
                int(_mapping(value, "checkpoint")["bytes"]),
                str(_mapping(value, "checkpoint")["sha256"]),
                str(_mapping(value, "checkpoint")["model_id"]),
            )
            for value in checkpoint_values
        ]
        metrics_raw = saved.get("generation_metrics", [])
        if not isinstance(metrics_raw, list):
            raise ValueError("invalid generation metrics")
        generation_metrics = [_mapping(value, "generation metrics") for value in metrics_raw]

    if checkpoints:
        latest = checkpoints[-1]
        if sha256_file(latest.path) != latest.sha256:
            raise ValueError("latest lineage checkpoint hash mismatch")
        model, _metadata, optimizer_state = load_training_checkpoint(
            latest.path, device=config.device
        )
        optimizer = _make_optimizer(model, config.learner, optimizer_state)
        model_id = latest.model_id
    else:
        torch.manual_seed(config.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(config.seed)
        model = PolicyValueNet(config.network)
        model_id = f"{config.run_id}-initial"

    started = time.perf_counter()
    for generation in range(completed_generations, config.generations):
        require_artifact_capacity(paths["root"], expected_new_bytes=5 * 1024**3)
        if active_generation is None:
            active_generation = generation
            active_games = 0
        if active_generation != generation:
            raise RuntimeError("lineage progress generation is inconsistent")
        _atomic_json(
            progress_path,
            _progress_payload(
                config=config,
                config_path=config_path,
                config_hash=config_hash,
                git_commit=git_commit,
                completed_generations=completed_generations,
                active_generation=active_generation,
                active_games=active_games,
                shards=shards,
                checkpoints=checkpoints,
                generation_metrics=generation_metrics,
            ),
        )
        evaluator = TorchEvaluator(model, config.device)
        generation_directory = f"generation-{generation:04d}"
        generation_shards = [item for item in shards if generation_directory in item.path.parts]
        if sum(item.games for item in generation_shards) != active_games:
            raise RuntimeError("active shard summaries do not match active game count")
        while active_games < config.games_per_generation:
            shard_game_count = min(
                config.games_per_shard,
                config.games_per_generation - active_games,
            )
            generated: list[SelfPlayGame] = []
            while len(generated) < shard_game_count:
                wave = min(config.actor_batch_size, shard_game_count - len(generated))
                first = active_games + len(generated)
                indices = list(range(first, first + wave))
                seeds = [config.seed + generation * 1_000_000 + index for index in indices]
                ids = [f"{config.run_id}-g{generation:04d}-{index:08d}" for index in indices]
                generated.extend(
                    play_self_games(
                        evaluator,
                        config.self_play,
                        seeds=seeds,
                        model_id=model_id,
                        game_ids=ids,
                    )
                )
            shard_index = active_games // config.games_per_shard
            output = (
                replay_path / f"generation-{generation:04d}" / f"shard-{shard_index:05d}.parquet"
            )
            if output.exists():
                raise FileExistsError(f"untracked lineage shard already exists: {output}")
            summary = write_training_shard(
                output,
                generated,
                metadata={
                    "run_id": config.run_id,
                    "lineage": config.lineage,
                    "generation": generation,
                    "model_id": model_id,
                    "git_commit": git_commit,
                    "config_sha256": config_hash,
                },
            )
            shards.append(summary)
            generation_shards.append(summary)
            active_games += shard_game_count
            _atomic_json(
                progress_path,
                _progress_payload(
                    config=config,
                    config_path=config_path,
                    config_hash=config_hash,
                    git_commit=git_commit,
                    completed_generations=completed_generations,
                    active_generation=active_generation,
                    active_games=active_games,
                    shards=shards,
                    checkpoints=checkpoints,
                    generation_metrics=generation_metrics,
                ),
            )
            emit(
                f"generation {generation + 1}/{config.generations}: "
                f"self-play {active_games}/{config.games_per_generation}"
            )

        replay_window = shards[-config.replay_window_shards :]
        training_batch = load_training_sample(
            (shard.path for shard in replay_window),
            maximum_positions=config.replay_sample_positions,
            seed=config.seed + generation,
        )
        optimizer, metrics = train_model(
            model,
            training_batch,
            config.learner,
            device=config.device,
            seed=config.seed + generation,
            optimizer=optimizer,
        )
        output_checkpoint = checkpoint_path / f"generation-{generation:04d}.pt"
        if output_checkpoint.exists():
            raise FileExistsError(
                f"untracked lineage checkpoint already exists: {output_checkpoint}"
            )
        checkpoint = save_checkpoint(
            output_checkpoint,
            model,
            optimizer=optimizer,
            metadata={
                "run_id": config.run_id,
                "lineage": config.lineage,
                "generation": generation,
                "seed": config.seed,
                "git_commit": git_commit,
                "config_sha256": config_hash,
                "generation_data_sha256": [item.sha256 for item in generation_shards],
            },
        )
        checkpoints.append(checkpoint)
        model_id = checkpoint.model_id
        generation_metrics.append(
            {
                "generation": generation,
                "games": config.games_per_generation,
                "positions": sum(item.positions for item in generation_shards),
                "learner": asdict(metrics),
                "checkpoint_sha256": checkpoint.sha256,
            }
        )
        completed_generations = generation + 1
        active_generation = None
        active_games = 0
        _atomic_json(
            progress_path,
            _progress_payload(
                config=config,
                config_path=config_path,
                config_hash=config_hash,
                git_commit=git_commit,
                completed_generations=completed_generations,
                active_generation=None,
                active_games=0,
                shards=shards,
                checkpoints=checkpoints,
                generation_metrics=generation_metrics,
            ),
        )
        emit(f"generation {generation + 1}/{config.generations}: checkpoint {model_id}")

    if not checkpoints:
        raise AssertionError("lineage completed without a checkpoint")
    latest = checkpoints[-1]
    return LineageResult(
        config.run_id,
        git_commit,
        completed_generations,
        completed_generations * config.games_per_generation,
        latest.path,
        latest.sha256,
        progress_path,
        time.perf_counter() - started,
    )
