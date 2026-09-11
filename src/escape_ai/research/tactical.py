"""Configuration-driven audits of saved tactical positions."""

from __future__ import annotations

import json
import math
import os
import platform
import random
import statistics
import subprocess
import time
import uuid
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import duckdb
import torch
import yaml  # type: ignore[import-untyped]

from escape_ai import _escape_core
from escape_ai.paths import ensure_artifact_layout, require_artifact_capacity
from escape_ai.search import PositionEvaluator, PUCTSearch, TorchEvaluator
from escape_ai.training.checkpoint import load_checkpoint
from escape_ai.training.data import sha256_file

from .features import transition_features
from .games import ResearchGame, ResearchSearchConfig, play_research_games
from .runner import ModelReference, _restore_summaries

TACTICAL_AUDIT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SourceReference:
    parquet: str
    manifest: Path
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class PositionReference:
    position_id: str
    game_id: str
    ply: int
    state_hash: int
    expected_turn: str
    expected_ball: tuple[int, int]
    budgets: tuple[int, ...]
    target_actions: tuple[int, ...]
    expected_directions: Mapping[int, str | None]


@dataclass(frozen=True, slots=True)
class BranchReference:
    branch_id: str
    position_id: str
    actions: tuple[int, ...]
    games_per_action: int
    actor_batch_size: int
    seed: int
    search: ResearchSearchConfig


@dataclass(frozen=True, slots=True)
class TacticalAuditConfig:
    run_id: str
    seed: int
    device: str
    c_puct: float
    parallel_leaves: int
    require_clean_worktree: bool
    source: SourceReference
    checkpoint: ModelReference
    positions: tuple[PositionReference, ...]
    branches: tuple[BranchReference, ...]


@dataclass(frozen=True, slots=True)
class TacticalAuditResult:
    run_id: str
    git_commit: str
    output: Path
    output_sha256: str
    elapsed_seconds: float


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _position_reference(value: object) -> PositionReference:
    raw = _mapping(value, "position")
    expected = _mapping(raw.get("expected", {}), "position expected values")
    directions = _mapping(expected.get("action_directions", {}), "action directions")
    ball = tuple(int(item) for item in expected["ball"])
    if len(ball) != 2:
        raise ValueError("expected ball must contain row and column")
    return PositionReference(
        position_id=str(raw["id"]),
        game_id=str(raw["game_id"]),
        ply=int(raw["ply"]),
        state_hash=int(raw["state_hash"]),
        expected_turn=str(expected["turn"]),
        expected_ball=(ball[0], ball[1]),
        budgets=tuple(int(item) for item in raw["budgets"]),
        target_actions=tuple(int(item) for item in raw["target_actions"]),
        expected_directions={
            int(action): None if direction is None else str(direction)
            for action, direction in directions.items()
        },
    )


def _branch_reference(value: object) -> BranchReference:
    raw = _mapping(value, "branch")
    return BranchReference(
        branch_id=str(raw["id"]),
        position_id=str(raw["position_id"]),
        actions=tuple(int(item) for item in raw["actions"]),
        games_per_action=int(raw["games_per_action"]),
        actor_batch_size=int(raw["actor_batch_size"]),
        seed=int(raw["seed"]),
        search=ResearchSearchConfig(**dict(_mapping(raw["search"], "branch search"))),
    )


def load_tactical_audit_config(path: Path) -> TacticalAuditConfig:
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "tactical audit")
    if raw.get("schema_version") != TACTICAL_AUDIT_SCHEMA_VERSION:
        raise ValueError("unsupported tactical-audit configuration schema")
    source_raw = _mapping(raw["source"], "source")
    checkpoint_raw = _mapping(raw["checkpoint"], "checkpoint")
    config = TacticalAuditConfig(
        run_id=str(raw["run_id"]),
        seed=int(raw["seed"]),
        device=str(raw.get("device", "cuda")),
        c_puct=float(raw.get("c_puct", 1.5)),
        parallel_leaves=int(raw.get("parallel_leaves", 16)),
        require_clean_worktree=bool(raw.get("require_clean_worktree", True)),
        source=SourceReference(
            parquet=str(source_raw["parquet"]),
            manifest=Path(str(source_raw["manifest"])),
            manifest_sha256=str(source_raw["manifest_sha256"]),
        ),
        checkpoint=ModelReference(
            Path(str(checkpoint_raw["path"])), str(checkpoint_raw["sha256"])
        ),
        positions=tuple(_position_reference(item) for item in raw["positions"]),
        branches=tuple(_branch_reference(item) for item in raw.get("branches", [])),
    )
    if not config.run_id or not config.positions:
        raise ValueError("tactical audit requires a run ID and at least one position")
    if config.parallel_leaves < 1 or config.c_puct <= 0.0:
        raise ValueError("root search settings must be positive")
    position_ids = [item.position_id for item in config.positions]
    if len(position_ids) != len(set(position_ids)):
        raise ValueError("position IDs must be unique")
    if any(not item.budgets or min(item.budgets) < 1 for item in config.positions):
        raise ValueError("position budgets must be positive")
    if any(not item.target_actions for item in config.positions):
        raise ValueError("positions require at least one target action")
    known_positions = set(position_ids)
    for branch in config.branches:
        if branch.position_id not in known_positions:
            raise ValueError(f"unknown branch position: {branch.position_id}")
        if (
            not branch.actions
            or branch.games_per_action < 1
            or branch.actor_batch_size < 1
            or branch.games_per_action % branch.actor_batch_size
        ):
            raise ValueError("branch counts must be positive and exactly batchable")
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


def _hardware(device: str) -> dict[str, object]:
    selected = torch.device(device)
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "device": device,
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
        "gpu": (
            torch.cuda.get_device_name(selected)
            if selected.type == "cuda" and torch.cuda.is_available()
            else None
        ),
    }


def _validate_source(source: SourceReference) -> Mapping[str, Any]:
    if sha256_file(source.manifest) != source.manifest_sha256:
        raise ValueError(f"source manifest hash mismatch: {source.manifest}")
    raw = _mapping(json.loads(source.manifest.read_text(encoding="utf-8")), "source manifest")
    _restore_summaries(raw.get("shards", []))
    return raw


def _load_position(source: str, reference: PositionReference) -> _escape_core.State:
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            """
            SELECT state, state_hash, turn, ball_row, ball_col, board_size
            FROM read_parquet(?) WHERE game_id = ? AND ply = ?
            """,
            [source, reference.game_id, reference.ply],
        ).fetchall()
    finally:
        connection.close()
    if len(rows) != 1:
        raise ValueError(
            f"expected one saved position for {reference.game_id} ply {reference.ply}, "
            f"found {len(rows)}"
        )
    payload, recorded_hash, turn, ball_row, ball_col, board_size = rows[0]
    state = _escape_core.State.deserialize(bytes(payload))
    if int(recorded_hash) != reference.state_hash or state.hash() != reference.state_hash:
        raise ValueError(f"state hash mismatch for position {reference.position_id}")
    expected = (reference.expected_turn, reference.expected_ball)
    recorded = (str(turn), (int(ball_row), int(ball_col)))
    decoded = (state.turn, state.ball)
    if (
        recorded != expected
        or decoded != expected
        or state.size != int(board_size)
        or state.ply != reference.ply
    ):
        raise ValueError(f"saved position metadata mismatch for {reference.position_id}")
    return state


def _policy_entropy(policy: Any) -> float:
    return -sum(float(value) * math.log(float(value)) for value in policy if value > 0.0)


def _transition(state: _escape_core.State, action: int) -> dict[str, object]:
    if state.legal_move_kind(action) is None:
        raise ValueError(f"action {action} is illegal at ply {state.ply}")
    after = state.apply(action)
    feature = transition_features(state, action, after, compute_reply_resistance=True)
    row, col = divmod(action, state.size + 1)
    return {
        "action": action,
        "vertex": [row, col],
        "move_kind": feature.move_kind,
        "ball_before": list(state.ball),
        "ball_after": list(after.ball),
        "ball_direction": feature.ball_move_direction,
        "new_walls": feature.new_walls,
        "reply_resistance": feature.reply_resistance,
        "outcome": dict(after.outcome),
    }


def audit_root_position(
    state: _escape_core.State,
    evaluator: PositionEvaluator,
    reference: PositionReference,
    *,
    c_puct: float,
    parallel_leaves: int,
    seed: int,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Run deterministic PUCT budgets and retain target-action ranks."""

    emit = progress or (lambda _message: None)
    for action, expected_direction in reference.expected_directions.items():
        actual = _transition(state, action)["ball_direction"]
        if actual != expected_direction:
            raise ValueError(
                f"action {action} direction mismatch: expected {expected_direction}, found {actual}"
            )
    searches: list[dict[str, object]] = []
    for budget_index, budget in enumerate(reference.budgets):
        search = PUCTSearch(
            evaluator,
            simulations=budget,
            c_puct=c_puct,
            parallel_leaves=parallel_leaves,
        )
        result = search.run(
            state,
            random.Random(seed + budget_index),
            temperature=0.0,
            add_root_noise=False,
            include_statistics=True,
        )
        ranked = {item.action: (rank, item) for rank, item in enumerate(result.statistics, 1)}
        targets: list[dict[str, object]] = []
        for action in reference.target_actions:
            if action not in ranked:
                raise ValueError(f"target action {action} is illegal for {reference.position_id}")
            rank, item = ranked[action]
            targets.append(
                {
                    **_transition(state, action),
                    "rank": rank,
                    "prior": item.prior,
                    "visits": item.visits,
                    "mean_value": item.mean_value,
                }
            )
        searches.append(
            {
                "simulations": budget,
                "selected_action": result.action,
                "root_value": result.root_value,
                "policy_entropy": _policy_entropy(result.policy),
                "targets": targets,
                "top_actions": [
                    {
                        "action": item.action,
                        "rank": rank,
                        "prior": item.prior,
                        "visits": item.visits,
                        "mean_value": item.mean_value,
                    }
                    for rank, item in enumerate(result.statistics[:20], 1)
                ],
            }
        )
        emit(f"root audit {reference.position_id}: {budget} simulations")
    return {
        "position_id": reference.position_id,
        "game_id": reference.game_id,
        "ply": reference.ply,
        "state_hash": reference.state_hash,
        "turn": state.turn,
        "ball": list(state.ball),
        "legal_actions": len(state.legal_actions()),
        "searches": searches,
    }


def _game_summary(game: ResearchGame, initial_ply: int) -> dict[str, object]:
    return {
        "game_id": game.game_id,
        "seed": game.seed,
        "winner": game.winner,
        "reason": game.reason,
        "continuation_plies": len(game.moves),
        "final_ply": initial_ply + len(game.moves),
        "ball_moves": sum(move.transition.ball_moved for move in game.moves),
        "replacements": sum(move.transition.move_kind == "replace" for move in game.moves),
    }


def _numeric_summary(values: list[int]) -> dict[str, float | int]:
    return {
        "minimum": min(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "maximum": max(values),
    }


def audit_forced_branches(
    state: _escape_core.State,
    evaluator: PositionEvaluator,
    reference: BranchReference,
    *,
    run_id: str,
    model_id: str,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Play matched-seed continuations after each forced action."""

    emit = progress or (lambda _message: None)
    seeds = [reference.seed + index for index in range(reference.games_per_action)]
    branch_results: list[dict[str, object]] = []
    for action in reference.actions:
        transition = _transition(state, action)
        initial = state.apply(action)
        if initial.outcome["status"] != "playing":
            raise ValueError(f"forced branch action {action} is terminal")
        games: list[ResearchGame] = []
        for first in range(0, reference.games_per_action, reference.actor_batch_size):
            batch_seeds = seeds[first : first + reference.actor_batch_size]
            games.extend(
                play_research_games(
                    evaluator,
                    reference.search,
                    seeds=batch_seeds,
                    white_model_id=model_id,
                    black_evaluator=evaluator,
                    black_model_id=model_id,
                    game_ids=[
                        f"{run_id}-{reference.branch_id}-a{action}-{index:04d}"
                        for index in range(first, first + len(batch_seeds))
                    ],
                    initial_states=[initial] * len(batch_seeds),
                )
            )
            emit(
                f"branch {reference.branch_id} action {action}: "
                f"{len(games)}/{reference.games_per_action} games"
            )
        summaries = [_game_summary(game, initial.ply) for game in games]
        outcomes = Counter("draw" if game.winner is None else game.winner for game in games)
        reasons = Counter(game.reason for game in games)
        continuation_plies = [len(game.moves) for game in games]
        branch_results.append(
            {
                "forced_transition": transition,
                "games": len(games),
                "outcomes": dict(outcomes),
                "reasons": dict(reasons),
                "continuation_plies": _numeric_summary(continuation_plies),
                "records": summaries,
            }
        )
    return {
        "branch_id": reference.branch_id,
        "position_id": reference.position_id,
        "matched_seeds": seeds,
        "search": asdict(reference.search),
        "branches": branch_results,
    }


def run_tactical_audit(
    config_path: Path,
    *,
    repo_root: Path,
    progress: Callable[[str], None] | None = None,
) -> TacticalAuditResult:
    """Validate inputs, audit roots, and play forced matched-seed branches."""

    emit = progress or (lambda _message: None)
    config = load_tactical_audit_config(config_path)
    config_hash = sha256_file(config_path)
    git_commit = _git(repo_root, "rev-parse", "HEAD")
    if config.require_clean_worktree and _git(repo_root, "status", "--porcelain"):
        raise RuntimeError("formal tactical audits require a clean Git worktree")
    if sha256_file(config.checkpoint.path) != config.checkpoint.sha256:
        raise ValueError(f"checkpoint hash mismatch: {config.checkpoint.path}")
    source_manifest = _validate_source(config.source)
    paths = ensure_artifact_layout()
    require_artifact_capacity(paths["root"], expected_new_bytes=1024**3)
    output = paths["runs"] / config.run_id / "result.json"
    if output.exists():
        saved = _mapping(json.loads(output.read_text(encoding="utf-8")), "tactical result")
        if saved.get("config_sha256") != config_hash or saved.get("git_commit") != git_commit:
            raise RuntimeError("existing tactical result belongs to another config or commit")
        return TacticalAuditResult(config.run_id, git_commit, output, sha256_file(output), 0.0)

    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)
    model, _ = load_checkpoint(config.checkpoint.path, device=config.device)
    evaluator = TorchEvaluator(model, config.device)
    states = {
        reference.position_id: _load_position(config.source.parquet, reference)
        for reference in config.positions
    }
    for branch in config.branches:
        if states[branch.position_id].size != branch.search.board_size:
            raise ValueError(f"branch board size mismatch: {branch.branch_id}")
    started = time.perf_counter()
    root_results = [
        audit_root_position(
            states[reference.position_id],
            evaluator,
            reference,
            c_puct=config.c_puct,
            parallel_leaves=config.parallel_leaves,
            seed=config.seed + position_index * 10_000,
            progress=emit,
        )
        for position_index, reference in enumerate(config.positions)
    ]
    branch_results = [
        audit_forced_branches(
            states[reference.position_id],
            evaluator,
            reference,
            run_id=config.run_id,
            model_id=config.checkpoint.model_id,
            progress=emit,
        )
        for reference in config.branches
    ]
    elapsed = time.perf_counter() - started
    result: dict[str, object] = {
        "schema_version": TACTICAL_AUDIT_SCHEMA_VERSION,
        "run_id": config.run_id,
        "git_commit": git_commit,
        "config_path": str(config_path.resolve()),
        "config_sha256": config_hash,
        "seed": config.seed,
        "elapsed_seconds": elapsed,
        "hardware": _hardware(config.device),
        "source": {
            "parquet": config.source.parquet,
            "manifest": str(config.source.manifest),
            "manifest_sha256": config.source.manifest_sha256,
            "generation_git_commit": source_manifest.get("git_commit"),
        },
        "checkpoint": {
            "path": str(config.checkpoint.path),
            "sha256": config.checkpoint.sha256,
            "model_id": config.checkpoint.model_id,
        },
        "root_search": {
            "c_puct": config.c_puct,
            "parallel_leaves": config.parallel_leaves,
            "positions": root_results,
        },
        "forced_branches": branch_results,
    }
    _atomic_json(output, result)
    return TacticalAuditResult(config.run_id, git_commit, output, sha256_file(output), elapsed)
