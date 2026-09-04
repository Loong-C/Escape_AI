"""Resumable configuration-driven generation of research-grade games."""

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

import yaml  # type: ignore[import-untyped]

from escape_ai.paths import ensure_artifact_layout, require_artifact_capacity
from escape_ai.search import TorchEvaluator
from escape_ai.training.checkpoint import load_checkpoint
from escape_ai.training.data import sha256_file

from .data import ResearchShardSummary, write_research_shard
from .games import ResearchGame, ResearchSearchConfig, play_research_games

RESEARCH_RUN_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ModelReference:
    path: Path
    sha256: str

    @property
    def model_id(self) -> str:
        return self.sha256[:16]


@dataclass(frozen=True, slots=True)
class ResearchRunConfig:
    run_id: str
    tier: str
    seed: int
    games: int
    games_per_shard: int
    actor_batch_size: int
    device: str
    paired_colors: bool
    white: ModelReference
    black: ModelReference
    search: ResearchSearchConfig
    require_clean_worktree: bool = True


@dataclass(frozen=True, slots=True)
class ResearchRunResult:
    run_id: str
    git_commit: str
    games: int
    moves: int
    shards: int
    elapsed_seconds: float
    progress_path: Path


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _model_reference(value: object, label: str) -> ModelReference:
    raw = _mapping(value, label)
    return ModelReference(Path(str(raw["path"])), str(raw["sha256"]))


def load_research_run_config(path: Path) -> ResearchRunConfig:
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "research run")
    if raw.get("schema_version") != RESEARCH_RUN_SCHEMA_VERSION:
        raise ValueError("unsupported research-run configuration schema")
    config = ResearchRunConfig(
        run_id=str(raw["run_id"]),
        tier=str(raw["tier"]),
        seed=int(raw["seed"]),
        games=int(raw["games"]),
        games_per_shard=int(raw["games_per_shard"]),
        actor_batch_size=int(raw["actor_batch_size"]),
        device=str(raw.get("device", "cuda")),
        paired_colors=bool(raw.get("paired_colors", True)),
        white=_model_reference(raw["white_checkpoint"], "white checkpoint"),
        black=_model_reference(raw["black_checkpoint"], "black checkpoint"),
        search=ResearchSearchConfig(**dict(_mapping(raw["search"], "search"))),
        require_clean_worktree=bool(raw.get("require_clean_worktree", True)),
    )
    if min(config.games, config.games_per_shard, config.actor_batch_size) < 1:
        raise ValueError("research game counts and batch size must be positive")
    if config.games % config.games_per_shard != 0:
        raise ValueError("games must be divisible by games_per_shard")
    if config.paired_colors and config.games % 2:
        raise ValueError("paired-color research runs require an even game count")
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


def _restore_summaries(raw: object) -> list[ResearchShardSummary]:
    if not isinstance(raw, list):
        raise ValueError("invalid research shard progress")
    summaries: list[ResearchShardSummary] = []
    for value in raw:
        item = _mapping(value, "research shard")
        summary = ResearchShardSummary(
            Path(str(item["path"])),
            int(item["games"]),
            int(item["moves"]),
            int(item["bytes"]),
            str(item["sha256"]),
        )
        if not summary.path.is_file():
            raise FileNotFoundError(summary.path)
        summaries.append(summary)
    return summaries


def _generate_side(
    indices: list[int],
    *,
    config: ResearchRunConfig,
    white_evaluator: TorchEvaluator,
    black_evaluator: TorchEvaluator,
    white_id: str,
    black_id: str,
) -> list[ResearchGame]:
    return play_research_games(
        white_evaluator,
        config.search,
        seeds=[
            config.seed
            + (
                index // 2
                if config.paired_colors and config.white.sha256 != config.black.sha256
                else index
            )
            for index in indices
        ],
        white_model_id=white_id,
        game_ids=[f"{config.run_id}-{index:08d}" for index in indices],
        black_evaluator=black_evaluator,
        black_model_id=black_id,
    )


def run_research_games(
    config_path: Path,
    *,
    repo_root: Path,
    progress: Callable[[str], None] | None = None,
) -> ResearchRunResult:
    emit = progress or (lambda _message: None)
    config = load_research_run_config(config_path)
    config_hash = sha256_file(config_path)
    git_commit = _git(repo_root, "rev-parse", "HEAD")
    if config.require_clean_worktree and _git(repo_root, "status", "--porcelain"):
        raise RuntimeError("formal research runs require a clean Git worktree")
    for reference in (config.white, config.black):
        if sha256_file(reference.path) != reference.sha256:
            raise ValueError(f"checkpoint hash mismatch: {reference.path}")
    paths = ensure_artifact_layout()
    require_artifact_capacity(paths["root"], expected_new_bytes=5 * 1024**3)
    progress_path = paths["runs"] / config.run_id / "progress.json"
    summaries: list[ResearchShardSummary] = []
    completed = 0
    if progress_path.exists():
        saved = _mapping(json.loads(progress_path.read_text(encoding="utf-8")), "progress")
        if saved.get("config_sha256") != config_hash or saved.get("git_commit") != git_commit:
            raise RuntimeError("cannot resume research run with different config or Git commit")
        summaries = _restore_summaries(saved.get("shards", []))
        completed = int(saved.get("completed_games", 0))
        if sum(item.games for item in summaries) != completed:
            raise RuntimeError("research shard summaries do not match completed game count")

    white_model, _ = load_checkpoint(config.white.path, device=config.device)
    white_evaluator = TorchEvaluator(white_model, config.device)
    if config.black.path == config.white.path:
        black_evaluator = white_evaluator
    else:
        black_model, _ = load_checkpoint(config.black.path, device=config.device)
        black_evaluator = TorchEvaluator(black_model, config.device)

    started = time.perf_counter()
    while completed < config.games:
        count = min(config.games_per_shard, config.games - completed)
        generated: list[ResearchGame] = []
        while len(generated) < count:
            wave = min(config.actor_batch_size, count - len(generated))
            first = completed + len(generated)
            indices = list(range(first, first + wave))
            if config.paired_colors and config.white.sha256 != config.black.sha256:
                even = [index for index in indices if index % 2 == 0]
                odd = [index for index in indices if index % 2 == 1]
                generated.extend(
                    _generate_side(
                        even,
                        config=config,
                        white_evaluator=white_evaluator,
                        black_evaluator=black_evaluator,
                        white_id=config.white.model_id,
                        black_id=config.black.model_id,
                    )
                )
                generated.extend(
                    _generate_side(
                        odd,
                        config=config,
                        white_evaluator=black_evaluator,
                        black_evaluator=white_evaluator,
                        white_id=config.black.model_id,
                        black_id=config.white.model_id,
                    )
                )
            else:
                generated.extend(
                    _generate_side(
                        indices,
                        config=config,
                        white_evaluator=white_evaluator,
                        black_evaluator=black_evaluator,
                        white_id=config.white.model_id,
                        black_id=config.black.model_id,
                    )
                )
        shard_index = completed // config.games_per_shard
        output = paths["games"] / config.run_id / f"shard-{shard_index:05d}.parquet"
        if output.exists():
            raise FileExistsError(f"untracked research shard already exists: {output}")
        summary = write_research_shard(
            output,
            generated,
            metadata={
                "run_id": config.run_id,
                "tier": config.tier,
                "git_commit": git_commit,
                "config_sha256": config_hash,
                "white_checkpoint_sha256": config.white.sha256,
                "black_checkpoint_sha256": config.black.sha256,
            },
        )
        summaries.append(summary)
        completed += count
        _atomic_json(
            progress_path,
            {
                "schema_version": RESEARCH_RUN_SCHEMA_VERSION,
                "run_id": config.run_id,
                "tier": config.tier,
                "git_commit": git_commit,
                "config_path": str(config_path.resolve()),
                "config_sha256": config_hash,
                "completed_games": completed,
                "target_games": config.games,
                "moves": sum(item.moves for item in summaries),
                "shards": [{**asdict(item), "path": str(item.path)} for item in summaries],
            },
        )
        emit(f"research games {completed}/{config.games}")

    return ResearchRunResult(
        config.run_id,
        git_commit,
        completed,
        sum(item.moves for item in summaries),
        len(summaries),
        time.perf_counter() - started,
        progress_path,
    )
