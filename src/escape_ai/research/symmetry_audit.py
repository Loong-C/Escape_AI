"""Role-aware symmetry audits for trained Escape checkpoints."""

from __future__ import annotations

import json
import random
import statistics
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import numpy.typing as npt
import torch
import yaml  # type: ignore[import-untyped]

from escape_ai import _escape_core
from escape_ai.paths import ensure_artifact_layout, require_artifact_capacity
from escape_ai.search import Evaluation, PositionEvaluator, PUCTSearch, SearchResult, TorchEvaluator
from escape_ai.training.checkpoint import load_checkpoint
from escape_ai.training.data import sha256_file

from .runner import ModelReference
from .tactical import SourceReference, _atomic_json, _git, _hardware, _validate_source

SYMMETRY_AUDIT_SCHEMA_VERSION = 1

_SYMMETRIES = (
    _escape_core.Symmetry.IDENTITY,
    _escape_core.Symmetry.ROTATE_90,
    _escape_core.Symmetry.ROTATE_180,
    _escape_core.Symmetry.ROTATE_270,
    _escape_core.Symmetry.FLIP_HORIZONTAL,
    _escape_core.Symmetry.FLIP_VERTICAL,
    _escape_core.Symmetry.DIAGONAL_MAIN,
    _escape_core.Symmetry.DIAGONAL_ANTI,
)
_AXIS_SWAPPING = frozenset(
    {
        _escape_core.Symmetry.ROTATE_90,
        _escape_core.Symmetry.ROTATE_270,
        _escape_core.Symmetry.DIAGONAL_MAIN,
        _escape_core.Symmetry.DIAGONAL_ANTI,
    }
)
_PHASES = ("opening", "middlegame", "late")
_TURNS = ("white", "black")


@dataclass(frozen=True, slots=True)
class SearchAuditConfig:
    samples_per_stratum: int
    simulations: int
    c_puct: float
    parallel_leaves: int


@dataclass(frozen=True, slots=True)
class DecisionThresholds:
    maximum_neural_p95_value_error: float
    maximum_neural_p95_policy_l1: float
    minimum_neural_top1_agreement: float
    minimum_neural_top5_overlap: float
    minimum_search_selected_agreement: float
    minimum_search_top5_overlap: float


@dataclass(frozen=True, slots=True)
class SymmetryAuditConfig:
    run_id: str
    seed: int
    device: str
    inference_batch_size: int
    samples_per_stratum: int
    require_clean_worktree: bool
    source: SourceReference
    checkpoint: ModelReference
    search: SearchAuditConfig
    decision_thresholds: DecisionThresholds


@dataclass(frozen=True, slots=True)
class SavedSample:
    game_id: str
    ply: int
    state_hash: int
    phase: str
    turn: str
    state: _escape_core.State


@dataclass(frozen=True, slots=True)
class NeuralMetric:
    game_id: str
    ply: int
    state_hash: int
    phase: str
    turn: str
    symmetry: str
    transformation_class: str
    value_absolute_error: float
    policy_l1: float
    policy_js: float
    top1_agreement: bool
    top5_overlap: float


@dataclass(frozen=True, slots=True)
class SearchMetric:
    game_id: str
    ply: int
    state_hash: int
    phase: str
    turn: str
    symmetry: str
    transformation_class: str
    root_value_absolute_error: float
    policy_l1: float
    policy_js: float
    selected_agreement: bool
    base_selected_rank_in_transformed: int
    transformed_selected_rank_in_base: int
    top5_overlap: float


@dataclass(frozen=True, slots=True)
class SymmetryAuditResult:
    run_id: str
    git_commit: str
    output: Path
    output_sha256: str
    elapsed_seconds: float


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def load_symmetry_audit_config(path: Path) -> SymmetryAuditConfig:
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "symmetry audit")
    if raw.get("schema_version") != SYMMETRY_AUDIT_SCHEMA_VERSION:
        raise ValueError("unsupported symmetry-audit configuration schema")
    source = _mapping(raw["source"], "source")
    checkpoint = _mapping(raw["checkpoint"], "checkpoint")
    search = _mapping(raw["search"], "search")
    thresholds = _mapping(raw["decision_thresholds"], "decision thresholds")
    config = SymmetryAuditConfig(
        run_id=str(raw["run_id"]),
        seed=int(raw["seed"]),
        device=str(raw.get("device", "cuda")),
        inference_batch_size=int(raw["inference_batch_size"]),
        samples_per_stratum=int(raw["samples_per_stratum"]),
        require_clean_worktree=bool(raw.get("require_clean_worktree", True)),
        source=SourceReference(
            parquet=str(source["parquet"]),
            manifest=Path(str(source["manifest"])),
            manifest_sha256=str(source["manifest_sha256"]),
        ),
        checkpoint=ModelReference(Path(str(checkpoint["path"])), str(checkpoint["sha256"])),
        search=SearchAuditConfig(
            samples_per_stratum=int(search["samples_per_stratum"]),
            simulations=int(search["simulations"]),
            c_puct=float(search["c_puct"]),
            parallel_leaves=int(search["parallel_leaves"]),
        ),
        decision_thresholds=DecisionThresholds(
            maximum_neural_p95_value_error=float(
                thresholds["maximum_neural_p95_value_error"]
            ),
            maximum_neural_p95_policy_l1=float(
                thresholds["maximum_neural_p95_policy_l1"]
            ),
            minimum_neural_top1_agreement=float(
                thresholds["minimum_neural_top1_agreement"]
            ),
            minimum_neural_top5_overlap=float(
                thresholds["minimum_neural_top5_overlap"]
            ),
            minimum_search_selected_agreement=float(
                thresholds["minimum_search_selected_agreement"]
            ),
            minimum_search_top5_overlap=float(
                thresholds["minimum_search_top5_overlap"]
            ),
        ),
    )
    counts = (
        config.inference_batch_size,
        config.samples_per_stratum,
        config.search.samples_per_stratum,
        config.search.simulations,
        config.search.parallel_leaves,
    )
    if not config.run_id or min(counts) < 1 or config.search.c_puct <= 0.0:
        raise ValueError("symmetry-audit counts and search constants must be positive")
    if config.search.samples_per_stratum > config.samples_per_stratum:
        raise ValueError("search sample count cannot exceed inference sample count")
    threshold_values = asdict(config.decision_thresholds)
    if any(not 0.0 <= value <= 1.0 for value in threshold_values.values()):
        raise ValueError("symmetry decision thresholds must be between zero and one")
    return config


def symmetry_swaps_roles(symmetry: _escape_core.Symmetry) -> bool:
    """Return whether a geometric symmetry exchanges horizontal/vertical goals."""

    return symmetry in _AXIS_SWAPPING


def transform_equivalent_state(
    state: _escape_core.State,
    symmetry: _escape_core.Symmetry,
) -> _escape_core.State:
    """Apply the core's game-equivalent D4 transform.

    The rules core swaps post colors, player-to-move, and any winner when the
    transform exchanges the horizontal and vertical goal axes.
    """

    if state.outcome["status"] != "playing":
        raise ValueError("role-aware transforms currently require a playing state")
    return state.transformed(symmetry)


def assert_legal_action_equivariance(
    state: _escape_core.State,
    transformed: _escape_core.State,
    symmetry: _escape_core.Symmetry,
) -> None:
    expected = {
        _escape_core.transform_action(action, state.size, symmetry)
        for action in state.legal_actions()
    }
    observed = set(transformed.legal_actions())
    if observed != expected:
        raise AssertionError(f"legal-action symmetry mismatch for {symmetry.name}")


def _phase(ply: int) -> str:
    if ply < 20:
        return "opening"
    if ply < 80:
        return "middlegame"
    return "late"


def _load_samples(source: str, samples_per_stratum: int, seed: int) -> list[SavedSample]:
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            """
            WITH labeled AS (
              SELECT game_id, ply, turn, state, state_hash,
                     CASE WHEN ply < 20 THEN 'opening'
                          WHEN ply < 80 THEN 'middlegame'
                          ELSE 'late' END phase,
                     row_number() OVER (
                       PARTITION BY state_hash,
                                    CASE WHEN ply < 20 THEN 'opening'
                                         WHEN ply < 80 THEN 'middlegame'
                                         ELSE 'late' END,
                                    turn
                       ORDER BY game_id, ply
                     ) duplicate_rank
              FROM read_parquet(?)
            )
            SELECT game_id, ply, state_hash, phase, turn, state
            FROM labeled WHERE duplicate_rank = 1
            ORDER BY phase, turn, game_id, ply
            """,
            [source],
        ).fetchall()
    finally:
        connection.close()
    grouped: dict[tuple[str, str], list[tuple[Any, ...]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row[3]), str(row[4]))].append(row)
    rng = random.Random(seed)
    samples: list[SavedSample] = []
    for phase in _PHASES:
        for turn in _TURNS:
            candidates = grouped[(phase, turn)]
            if len(candidates) < samples_per_stratum:
                raise ValueError(
                    f"stratum {phase}/{turn} contains {len(candidates)} distinct states, "
                    f"needs {samples_per_stratum}"
                )
            selected = rng.sample(candidates, samples_per_stratum)
            selected.sort(key=lambda row: (str(row[0]), int(row[1])))
            for game_id, ply, state_hash, recorded_phase, recorded_turn, payload in selected:
                state = _escape_core.State.deserialize(bytes(payload))
                if (
                    state.hash() != int(state_hash)
                    or state.ply != int(ply)
                    or state.turn != str(recorded_turn)
                    or _phase(state.ply) != str(recorded_phase)
                ):
                    raise ValueError(f"invalid saved state: {game_id} ply {ply}")
                samples.append(
                    SavedSample(
                        str(game_id),
                        int(ply),
                        int(state_hash),
                        str(recorded_phase),
                        str(recorded_turn),
                        state,
                    )
                )
    return samples


def _evaluate_batches(
    evaluator: PositionEvaluator,
    states: Sequence[_escape_core.State],
    batch_size: int,
    progress: Callable[[str], None],
) -> list[Evaluation]:
    evaluations: list[Evaluation] = []
    for first in range(0, len(states), batch_size):
        evaluations.extend(evaluator.evaluate(states[first : first + batch_size]))
        progress(f"symmetry inference {len(evaluations)}/{len(states)} states")
    return evaluations


def _mapped_policy(
    state: _escape_core.State,
    transformed_policy: npt.NDArray[np.float32],
    symmetry: _escape_core.Symmetry,
) -> npt.NDArray[np.float32]:
    mapped = np.zeros_like(transformed_policy)
    for action in state.legal_actions():
        mapped[action] = transformed_policy[
            _escape_core.transform_action(action, state.size, symmetry)
        ]
    return mapped


def _top_actions(
    state: _escape_core.State,
    policy: npt.NDArray[np.float32],
    count: int,
) -> tuple[int, ...]:
    ranked = sorted(state.legal_actions(), key=lambda action: (-policy[action], action))
    return tuple(ranked[:count])


def _policy_metrics(
    state: _escape_core.State,
    expected: npt.NDArray[np.float32],
    observed: npt.NDArray[np.float32],
) -> tuple[float, float, bool, float]:
    legal = np.asarray(state.legal_actions(), dtype=np.int64)
    left = expected[legal].astype(np.float64)
    right = observed[legal].astype(np.float64)
    midpoint = 0.5 * (left + right)
    left_positive = left > 0.0
    right_positive = right > 0.0
    left_kl = float(
        (left[left_positive] * np.log(left[left_positive] / midpoint[left_positive])).sum()
    )
    right_kl = float(
        (right[right_positive] * np.log(right[right_positive] / midpoint[right_positive])).sum()
    )
    js = 0.5 * (left_kl + right_kl)
    expected_top = _top_actions(state, expected, 5)
    observed_top = _top_actions(state, observed, 5)
    overlap = len(set(expected_top) & set(observed_top)) / 5.0
    return (
        float(np.abs(left - right).sum()),
        js,
        expected_top[0] == observed_top[0],
        overlap,
    )


def _transformation_class(symmetry: _escape_core.Symmetry) -> str:
    return "axis-swapping-role-swap" if symmetry_swaps_roles(symmetry) else "axis-preserving"


def _float_distribution(values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p95": float(np.quantile(array, 0.95)),
        "maximum": float(array.max()),
    }


def _neural_summary(records: Sequence[NeuralMetric]) -> dict[str, object]:
    return {
        "count": len(records),
        "value_absolute_error": _float_distribution(
            [item.value_absolute_error for item in records]
        ),
        "policy_l1": _float_distribution([item.policy_l1 for item in records]),
        "policy_js": _float_distribution([item.policy_js for item in records]),
        "top1_agreement": statistics.mean(item.top1_agreement for item in records),
        "mean_top5_overlap": statistics.mean(item.top5_overlap for item in records),
    }


def _search_summary(records: Sequence[SearchMetric]) -> dict[str, object]:
    return {
        "count": len(records),
        "root_value_absolute_error": _float_distribution(
            [item.root_value_absolute_error for item in records]
        ),
        "policy_l1": _float_distribution([item.policy_l1 for item in records]),
        "policy_js": _float_distribution([item.policy_js for item in records]),
        "selected_agreement": statistics.mean(item.selected_agreement for item in records),
        "mean_base_selected_rank_in_transformed": statistics.mean(
            item.base_selected_rank_in_transformed for item in records
        ),
        "mean_transformed_selected_rank_in_base": statistics.mean(
            item.transformed_selected_rank_in_base for item in records
        ),
        "mean_top5_overlap": statistics.mean(item.top5_overlap for item in records),
    }


def _grouped_summaries[Metric](
    records: Sequence[Metric],
    summary: Callable[[Sequence[Metric]], dict[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {"overall": summary(records)}
    for attribute, label in (
        ("transformation_class", "transformation_classes"),
        ("symmetry", "symmetries"),
        ("phase", "phases"),
        ("turn", "turns"),
    ):
        groups: dict[str, list[Metric]] = defaultdict(list)
        for record in records:
            groups[str(getattr(record, attribute))].append(record)
        result[label] = {name: summary(items) for name, items in sorted(groups.items())}
    return result


def _decision(
    neural_summary: Mapping[str, object],
    search_summary: Mapping[str, object],
    thresholds: DecisionThresholds,
) -> dict[str, object]:
    neural_overall = _mapping(neural_summary["overall"], "neural overall summary")
    search_overall = _mapping(search_summary["overall"], "search overall summary")
    value_error = _mapping(
        neural_overall["value_absolute_error"], "neural value-error summary"
    )
    policy_l1 = _mapping(neural_overall["policy_l1"], "neural policy-L1 summary")
    checks = {
        "neural_p95_value_error": (
            float(value_error["p95"]),
            "maximum",
            thresholds.maximum_neural_p95_value_error,
        ),
        "neural_p95_policy_l1": (
            float(policy_l1["p95"]),
            "maximum",
            thresholds.maximum_neural_p95_policy_l1,
        ),
        "neural_top1_agreement": (
            float(neural_overall["top1_agreement"]),
            "minimum",
            thresholds.minimum_neural_top1_agreement,
        ),
        "neural_mean_top5_overlap": (
            float(neural_overall["mean_top5_overlap"]),
            "minimum",
            thresholds.minimum_neural_top5_overlap,
        ),
        "search_selected_agreement": (
            float(search_overall["selected_agreement"]),
            "minimum",
            thresholds.minimum_search_selected_agreement,
        ),
        "search_mean_top5_overlap": (
            float(search_overall["mean_top5_overlap"]),
            "minimum",
            thresholds.minimum_search_top5_overlap,
        ),
    }
    outcomes = {
        name: {
            "observed": observed,
            "operator": operator,
            "threshold": threshold,
            "passed": observed <= threshold if operator == "maximum" else observed >= threshold,
        }
        for name, (observed, operator, threshold) in checks.items()
    }
    low_error = all(bool(item["passed"]) for item in outcomes.values())
    return {
        "classification": "low-symmetry-error" if low_error else "material-symmetry-error",
        "next_experiment": (
            "black-first-matched-seed-diagnostic"
            if low_error
            else "symmetry-ensemble-evaluator"
        ),
        "criteria": outcomes,
    }


def _neural_audit(
    samples: Sequence[SavedSample],
    evaluator: PositionEvaluator,
    batch_size: int,
    progress: Callable[[str], None],
) -> tuple[list[NeuralMetric], dict[str, object]]:
    transformed_states: list[_escape_core.State] = []
    for sample in samples:
        for symmetry in _SYMMETRIES:
            transformed_state = transform_equivalent_state(sample.state, symmetry)
            assert_legal_action_equivariance(sample.state, transformed_state, symmetry)
            transformed_states.append(transformed_state)
    evaluations = _evaluate_batches(evaluator, transformed_states, batch_size, progress)
    records: list[NeuralMetric] = []
    width = len(_SYMMETRIES)
    for sample_index, sample in enumerate(samples):
        base = evaluations[sample_index * width]
        for offset, symmetry in enumerate(_SYMMETRIES[1:], 1):
            transformed_evaluation = evaluations[sample_index * width + offset]
            mapped = _mapped_policy(sample.state, transformed_evaluation.priors, symmetry)
            l1, js, top1, top5 = _policy_metrics(sample.state, base.priors, mapped)
            records.append(
                NeuralMetric(
                    sample.game_id,
                    sample.ply,
                    sample.state_hash,
                    sample.phase,
                    sample.turn,
                    symmetry.name.lower(),
                    _transformation_class(symmetry),
                    abs(base.value - transformed_evaluation.value),
                    l1,
                    js,
                    top1,
                    top5,
                )
            )
    return records, _grouped_summaries(records, _neural_summary)


def _rank_by_action(result: SearchResult) -> dict[int, int]:
    return {item.action: rank for rank, item in enumerate(result.statistics, 1)}


def _search_audit(
    samples: Sequence[SavedSample],
    evaluator: PositionEvaluator,
    config: SearchAuditConfig,
    seed: int,
    progress: Callable[[str], None],
) -> tuple[list[SearchMetric], dict[str, object]]:
    grouped: dict[tuple[str, str], list[SavedSample]] = defaultdict(list)
    for sample in samples:
        grouped[(sample.phase, sample.turn)].append(sample)
    selected = [
        sample
        for phase in _PHASES
        for turn in _TURNS
        for sample in sorted(
            random.Random(f"{seed}:{phase}:{turn}").sample(
                grouped[(phase, turn)], config.samples_per_stratum
            ),
            key=lambda item: (item.game_id, item.ply),
        )
    ]
    records: list[SearchMetric] = []
    for sample_index, sample in enumerate(selected):
        states = [transform_equivalent_state(sample.state, symmetry) for symmetry in _SYMMETRIES]
        search = PUCTSearch(
            evaluator,
            simulations=config.simulations,
            c_puct=config.c_puct,
            parallel_leaves=config.parallel_leaves,
        )
        results = search.run_batch(
            states,
            [random.Random(seed + sample_index) for _symmetry in _SYMMETRIES],
            temperatures=[0.0] * len(_SYMMETRIES),
            add_root_noise=False,
            include_statistics=True,
        )
        base = results[0]
        base_ranks = _rank_by_action(base)
        for offset, symmetry in enumerate(_SYMMETRIES[1:], 1):
            transformed = results[offset]
            transformed_ranks = _rank_by_action(transformed)
            mapped = _mapped_policy(sample.state, transformed.policy, symmetry)
            l1, js, selected_agreement, top5 = _policy_metrics(
                sample.state, base.policy, mapped
            )
            action_map = {
                _escape_core.transform_action(action, sample.state.size, symmetry): action
                for action in sample.state.legal_actions()
            }
            mapped_selected = action_map[transformed.action]
            records.append(
                SearchMetric(
                    sample.game_id,
                    sample.ply,
                    sample.state_hash,
                    sample.phase,
                    sample.turn,
                    symmetry.name.lower(),
                    _transformation_class(symmetry),
                    abs(base.root_value - transformed.root_value),
                    l1,
                    js,
                    selected_agreement,
                    transformed_ranks[
                        _escape_core.transform_action(base.action, sample.state.size, symmetry)
                    ],
                    base_ranks[mapped_selected],
                    top5,
                )
            )
        progress(f"symmetry PUCT {sample_index + 1}/{len(selected)} positions")
    return records, _grouped_summaries(records, _search_summary)


def run_symmetry_audit(
    config_path: Path,
    *,
    repo_root: Path,
    progress: Callable[[str], None] | None = None,
) -> SymmetryAuditResult:
    """Run a provenance-complete role-aware checkpoint symmetry audit."""

    emit = progress or (lambda _message: None)
    config = load_symmetry_audit_config(config_path)
    config_hash = sha256_file(config_path)
    git_commit = _git(repo_root, "rev-parse", "HEAD")
    if config.require_clean_worktree and _git(repo_root, "status", "--porcelain"):
        raise RuntimeError("formal symmetry audits require a clean Git worktree")
    if sha256_file(config.checkpoint.path) != config.checkpoint.sha256:
        raise ValueError(f"checkpoint hash mismatch: {config.checkpoint.path}")
    source_manifest = _validate_source(config.source)
    paths = ensure_artifact_layout()
    require_artifact_capacity(paths["root"], expected_new_bytes=1024**3)
    output = paths["runs"] / config.run_id / "result.json"
    if output.exists():
        saved = _mapping(json.loads(output.read_text(encoding="utf-8")), "symmetry result")
        if saved.get("config_sha256") != config_hash or saved.get("git_commit") != git_commit:
            raise RuntimeError("existing symmetry result belongs to another config or commit")
        return SymmetryAuditResult(config.run_id, git_commit, output, sha256_file(output), 0.0)

    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)
    model, _ = load_checkpoint(config.checkpoint.path, device=config.device)
    evaluator = TorchEvaluator(model, config.device)
    samples = _load_samples(
        config.source.parquet,
        config.samples_per_stratum,
        config.seed,
    )
    started = time.perf_counter()
    neural_records, neural_summary = _neural_audit(
        samples,
        evaluator,
        config.inference_batch_size,
        emit,
    )
    search_records, search_summary = _search_audit(
        samples,
        evaluator,
        config.search,
        config.seed + 100_000,
        emit,
    )
    decision = _decision(neural_summary, search_summary, config.decision_thresholds)
    elapsed = time.perf_counter() - started
    result: dict[str, object] = {
        "schema_version": SYMMETRY_AUDIT_SCHEMA_VERSION,
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
        "sampling": {
            "samples_per_stratum": config.samples_per_stratum,
            "strata": [f"{phase}/{turn}" for phase in _PHASES for turn in _TURNS],
            "total_distinct_states": len(samples),
            "samples": [
                {
                    "game_id": sample.game_id,
                    "ply": sample.ply,
                    "state_hash": sample.state_hash,
                    "phase": sample.phase,
                    "turn": sample.turn,
                }
                for sample in samples
            ],
        },
        "neural": {
            "evaluations": len(samples) * len(_SYMMETRIES),
            "summary": neural_summary,
            "records": [asdict(item) for item in neural_records],
        },
        "search": {
            **asdict(config.search),
            "summary": search_summary,
            "records": [asdict(item) for item in search_records],
        },
        "decision": {
            "thresholds": asdict(config.decision_thresholds),
            **decision,
        },
    }
    _atomic_json(output, result)
    return SymmetryAuditResult(config.run_id, git_commit, output, sha256_file(output), elapsed)
