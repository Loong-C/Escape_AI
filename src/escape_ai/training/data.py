"""Atomic Parquet storage for self-play training positions."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pyarrow as pa
import pyarrow.parquet as pq

from escape_ai import _escape_core

from .encoding import encode_state, legal_action_mask
from .selfplay import SelfPlayGame

SCHEMA_VERSION = 1
TRAINING_D4_SYMMETRIES = (
    _escape_core.Symmetry.IDENTITY,
    _escape_core.Symmetry.ROTATE_90,
    _escape_core.Symmetry.ROTATE_180,
    _escape_core.Symmetry.ROTATE_270,
    _escape_core.Symmetry.FLIP_HORIZONTAL,
    _escape_core.Symmetry.FLIP_VERTICAL,
    _escape_core.Symmetry.DIAGONAL_MAIN,
    _escape_core.Symmetry.DIAGONAL_ANTI,
)


@dataclass(frozen=True, slots=True)
class ShardSummary:
    path: Path
    games: int
    positions: int
    bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class TrainingBatch:
    features: npt.NDArray[np.float32]
    policies: npt.NDArray[np.float32]
    legal_masks: npt.NDArray[np.bool_]
    values: npt.NDArray[np.float32]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def training_schema() -> Any:
    return pa.schema(
        [
            ("schema_version", pa.int16()),
            ("game_id", pa.string()),
            ("model_id", pa.string()),
            ("board_size", pa.int8()),
            ("seed", pa.int64()),
            ("ply", pa.int16()),
            ("turn", pa.string()),
            ("state", pa.binary()),
            ("policy", pa.list_(pa.float32())),
            ("root_value", pa.float32()),
            ("action", pa.int16()),
            ("value_target", pa.float32()),
            ("winner", pa.string()),
            ("reason", pa.string()),
        ]
    )


def _rows(games: Sequence[SelfPlayGame]) -> dict[str, list[object]]:
    columns: dict[str, list[object]] = {name: [] for name in training_schema().names}
    for game in games:
        for position in game.positions:
            columns["schema_version"].append(SCHEMA_VERSION)
            columns["game_id"].append(game.game_id)
            columns["model_id"].append(game.model_id)
            columns["board_size"].append(game.board_size)
            columns["seed"].append(game.seed)
            columns["ply"].append(position.ply)
            columns["turn"].append(position.turn)
            columns["state"].append(position.state)
            columns["policy"].append(position.policy.tolist())
            columns["root_value"].append(position.root_value)
            columns["action"].append(position.action)
            columns["value_target"].append(position.value_target)
            columns["winner"].append(game.winner)
            columns["reason"].append(game.reason)
    return columns


def write_training_shard(
    path: Path,
    games: Sequence[SelfPlayGame],
    *,
    metadata: Mapping[str, object] | None = None,
) -> ShardSummary:
    """Write a recoverable Parquet shard via temporary-file replacement."""

    if not games:
        raise ValueError("cannot write an empty training shard")
    board_sizes = {game.board_size for game in games}
    if len(board_sizes) != 1:
        raise ValueError("a training shard must contain one board size")
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = training_schema().with_metadata(
        {
            b"escape_ai": json.dumps(
                {"schema_version": SCHEMA_VERSION, **dict(metadata or {})},
                sort_keys=True,
            ).encode("utf-8")
        }
    )
    table = pa.Table.from_pydict(_rows(games), schema=schema)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        pq.write_table(  # type: ignore[no-untyped-call]
            table, temporary, compression="zstd", row_group_size=16_384
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return ShardSummary(
        path=path,
        games=len(games),
        positions=sum(game.plies for game in games),
        bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )


def load_training_batch(
    paths: Iterable[Path],
    *,
    symmetry_augmentation: str = "none",
    seed: int = 0,
) -> TrainingBatch:
    """Load same-size shards into arrays suitable for a learner smoke run."""

    tables = [pq.read_table(path) for path in paths]  # type: ignore[no-untyped-call]
    if not tables:
        raise ValueError("at least one training shard is required")
    return _table_to_training_batch(
        pa.concat_tables(tables),
        symmetry_augmentation=symmetry_augmentation,
        seed=seed,
    )


def load_training_sample(
    paths: Iterable[Path],
    *,
    maximum_positions: int,
    seed: int,
    symmetry_augmentation: str = "none",
) -> TrainingBatch:
    """Uniformly sample rows without materializing every replay shard."""

    selected_paths = list(paths)
    if not selected_paths or maximum_positions < 1:
        raise ValueError("replay paths and maximum_positions must be non-empty")
    row_counts = [
        pq.ParquetFile(path).metadata.num_rows  # type: ignore[no-untyped-call]
        for path in selected_paths
    ]
    total_rows = sum(row_counts)
    if maximum_positions >= total_rows:
        return load_training_batch(
            selected_paths,
            symmetry_augmentation=symmetry_augmentation,
            seed=seed,
        )

    rng = np.random.default_rng(seed)
    global_rows = np.sort(rng.choice(total_rows, size=maximum_positions, replace=False))
    tables: list[Any] = []
    offset = 0
    for path, row_count in zip(selected_paths, row_counts, strict=True):
        local = global_rows[(global_rows >= offset) & (global_rows < offset + row_count)] - offset
        offset += row_count
        if not len(local):
            continue
        table = pq.read_table(  # type: ignore[no-untyped-call]
            path,
            columns=["state", "policy", "value_target"],
        )
        tables.append(table.take(pa.array(local)))
    return _table_to_training_batch(
        pa.concat_tables(tables),
        symmetry_augmentation=symmetry_augmentation,
        seed=seed,
    )


def transform_training_position(
    state: _escape_core.State,
    policy: npt.NDArray[np.float32],
    symmetry: _escape_core.Symmetry,
) -> tuple[_escape_core.State, npt.NDArray[np.float32]]:
    """Apply one role-aware D4 transform to a state and its policy target."""

    action_count = (state.size + 1) ** 2
    if policy.shape != (action_count,):
        raise ValueError("policy target has the wrong action-space shape")
    transformed_policy = np.empty_like(policy)
    for action in range(action_count):
        target = _escape_core.transform_action(action, state.size, symmetry)
        transformed_policy[target] = policy[action]
    return state.transformed(symmetry), transformed_policy


def canonicalize_training_position(
    state: _escape_core.State,
    policy: npt.NDArray[np.float32],
) -> tuple[_escape_core.State, npt.NDArray[np.float32]]:
    """Map a training target to one D4-canonical state representation.

    If the position has a non-trivial stabilizer, every source-to-canonical
    transform is averaged. The resulting target is therefore invariant to the
    arbitrary transform chosen for a symmetric state.
    """

    transformed = [
        (*transform_training_position(state, policy, symmetry), index)
        for index, symmetry in enumerate(TRAINING_D4_SYMMETRIES)
    ]
    keyed = [
        (candidate_state.serialize(), index, candidate_state, candidate_policy)
        for candidate_state, candidate_policy, index in transformed
    ]
    key, _index, canonical, _policy = min(keyed, key=lambda item: (item[0], item[1]))
    policies = [
        candidate_policy
        for candidate_key, _, _, candidate_policy in keyed
        if candidate_key == key
    ]
    canonical_policy = np.mean(np.stack(policies).astype(np.float64), axis=0).astype(
        np.float32
    )
    return canonical, canonical_policy


def _table_to_training_batch(
    table: Any,
    *,
    symmetry_augmentation: str = "none",
    seed: int = 0,
) -> TrainingBatch:
    serialized_states = table.column("state").to_pylist()
    states = [_escape_core.State.deserialize(value) for value in serialized_states]
    board_sizes = {state.size for state in states}
    if len(board_sizes) != 1:
        raise ValueError("one training batch cannot mix board sizes")
    policies = np.asarray(table.column("policy").to_pylist(), dtype=np.float32)
    if symmetry_augmentation not in {"none", "random-d4", "canonical-d4"}:
        raise ValueError(
            f"unsupported training symmetry augmentation: {symmetry_augmentation}"
        )
    if symmetry_augmentation == "random-d4":
        rng = np.random.default_rng(seed)
        selections = rng.integers(0, len(TRAINING_D4_SYMMETRIES), size=len(states))
        transformed = [
            transform_training_position(state, policy, TRAINING_D4_SYMMETRIES[index])
            for state, policy, index in zip(states, policies, selections, strict=True)
        ]
        states = [item[0] for item in transformed]
        policies = np.stack([item[1] for item in transformed])
    elif symmetry_augmentation == "canonical-d4":
        transformed = [
            canonicalize_training_position(state, policy)
            for state, policy in zip(states, policies, strict=True)
        ]
        states = [item[0] for item in transformed]
        policies = np.stack([item[1] for item in transformed])
    return TrainingBatch(
        features=np.stack([encode_state(state) for state in states]),
        policies=policies,
        legal_masks=np.stack([legal_action_mask(state) for state in states]),
        values=np.asarray(table.column("value_target").to_pylist(), dtype=np.float32),
    )
