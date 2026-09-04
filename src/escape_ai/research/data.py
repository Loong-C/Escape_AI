"""Parquet schema for analysis-grade Escape game records."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from escape_ai.training.data import sha256_file

from .games import ResearchGame

RESEARCH_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ResearchShardSummary:
    path: Path
    games: int
    moves: int
    bytes: int
    sha256: str


def research_schema() -> Any:
    return pa.schema(
        [
            ("schema_version", pa.int16()),
            ("game_id", pa.string()),
            ("model_id", pa.string()),
            ("white_model_id", pa.string()),
            ("black_model_id", pa.string()),
            ("seed", pa.int64()),
            ("board_size", pa.int8()),
            ("search_simulations", pa.int32()),
            ("ply", pa.int16()),
            ("turn", pa.string()),
            ("state", pa.binary()),
            ("state_hash", pa.uint64()),
            ("ball_row", pa.int8()),
            ("ball_col", pa.int8()),
            ("legal_actions", pa.int16()),
            ("action", pa.int16()),
            ("move_kind", pa.string()),
            ("root_value", pa.float32()),
            ("policy_entropy", pa.float32()),
            ("candidate_actions", pa.list_(pa.int16())),
            ("candidate_priors", pa.list_(pa.float32())),
            ("candidate_visits", pa.list_(pa.int32())),
            ("candidate_values", pa.list_(pa.float32())),
            ("first_step_costs", pa.list_(pa.int32(), 4)),
            ("directional_exit_distances", pa.list_(pa.int32(), 4)),
            ("unique_gradient", pa.bool_()),
            ("gradient_delta", pa.int32()),
            ("white_posts", pa.int16()),
            ("black_posts", pa.int16()),
            ("white_floating", pa.int16()),
            ("black_floating", pa.int16()),
            ("white_anchored", pa.int16()),
            ("black_anchored", pa.int16()),
            ("white_walls", pa.int16()),
            ("black_walls", pa.int16()),
            ("new_walls", pa.int8()),
            ("ball_moved", pa.bool_()),
            ("ball_move_direction", pa.string()),
            ("reply_resistance", pa.int16()),
            ("winner", pa.string()),
            ("reason", pa.string()),
        ]
    )


def _rows(games: Sequence[ResearchGame]) -> dict[str, list[object]]:
    columns: dict[str, list[object]] = {name: [] for name in research_schema().names}
    for game in games:
        for move in game.moves:
            features = move.features
            transition = move.transition
            candidates = move.candidates
            values: dict[str, object] = {
                "schema_version": RESEARCH_SCHEMA_VERSION,
                "game_id": game.game_id,
                "model_id": (game.white_model_id if move.turn == "white" else game.black_model_id),
                "white_model_id": game.white_model_id,
                "black_model_id": game.black_model_id,
                "seed": game.seed,
                "board_size": game.board_size,
                "search_simulations": game.search_simulations,
                "ply": move.ply,
                "turn": move.turn,
                "state": move.state,
                "state_hash": move.state_hash,
                "ball_row": features.ball_row,
                "ball_col": features.ball_col,
                "legal_actions": features.legal_actions,
                "action": move.action,
                "move_kind": transition.move_kind,
                "root_value": move.root_value,
                "policy_entropy": move.policy_entropy,
                "candidate_actions": [item.action for item in candidates],
                "candidate_priors": [item.prior for item in candidates],
                "candidate_visits": [item.visits for item in candidates],
                "candidate_values": [item.mean_value for item in candidates],
                "first_step_costs": list(features.first_step_costs),
                "directional_exit_distances": list(features.directional_exit_distances),
                "unique_gradient": features.unique_gradient,
                "gradient_delta": features.gradient_delta,
                "white_posts": features.white_posts,
                "black_posts": features.black_posts,
                "white_floating": features.white_floating,
                "black_floating": features.black_floating,
                "white_anchored": features.white_anchored,
                "black_anchored": features.black_anchored,
                "white_walls": features.white_walls,
                "black_walls": features.black_walls,
                "new_walls": transition.new_walls,
                "ball_moved": transition.ball_moved,
                "ball_move_direction": transition.ball_move_direction,
                "reply_resistance": transition.reply_resistance,
                "winner": game.winner,
                "reason": game.reason,
            }
            for name in columns:
                columns[name].append(values[name])
    return columns


def write_research_shard(
    path: Path,
    games: Sequence[ResearchGame],
    *,
    metadata: Mapping[str, object] | None = None,
) -> ResearchShardSummary:
    if not games:
        raise ValueError("cannot write an empty research shard")
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = research_schema().with_metadata(
        {
            b"escape_ai": json.dumps(
                {"schema_version": RESEARCH_SCHEMA_VERSION, **dict(metadata or {})},
                sort_keys=True,
            ).encode("utf-8")
        }
    )
    table = pa.Table.from_pydict(_rows(games), schema=schema)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        pq.write_table(  # type: ignore[no-untyped-call]
            table,
            temporary,
            compression="zstd",
            row_group_size=8_192,
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return ResearchShardSummary(
        path,
        len(games),
        sum(len(game.moves) for game in games),
        path.stat().st_size,
        sha256_file(path),
    )
