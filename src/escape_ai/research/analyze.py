"""DuckDB summaries and tactical candidate mining for research games."""

from __future__ import annotations

import json
import math
import os
import uuid
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import duckdb

from escape_ai import _escape_core


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


def _entropy(counts: Counter[int]) -> float:
    total = sum(counts.values())
    return -sum((count / total) * math.log(count / total) for count in counts.values() if count)


def _canonical_action(action: int, size: int) -> int:
    symmetries = (
        _escape_core.Symmetry.IDENTITY,
        _escape_core.Symmetry.ROTATE_90,
        _escape_core.Symmetry.ROTATE_180,
        _escape_core.Symmetry.ROTATE_270,
        _escape_core.Symmetry.FLIP_HORIZONTAL,
        _escape_core.Symmetry.FLIP_VERTICAL,
        _escape_core.Symmetry.DIAGONAL_MAIN,
        _escape_core.Symmetry.DIAGONAL_ANTI,
    )
    return min(_escape_core.transform_action(action, size, symmetry) for symmetry in symmetries)


def analyze_research_games(input_glob: str, output: Path) -> dict[str, object]:
    """Summarize outcomes/diversity and retain the strongest tactical anomalies."""

    input_path = Path(input_glob)
    source = str(input_path / "*.parquet") if input_path.is_dir() else input_glob
    connection = duckdb.connect()
    overview_row = connection.execute(
        """
        WITH games AS (
          SELECT game_id, any_value(winner) winner, any_value(reason) reason,
                 max(ply) + 1 plies,
                 min(ply) FILTER (WHERE ball_moved) first_ball_move
          FROM read_parquet(?) GROUP BY game_id
        )
        SELECT count(*) games,
               sum(plies) moves,
               avg(plies) mean_plies,
               median(plies) median_plies,
               avg(first_ball_move) mean_first_ball_move,
               median(first_ball_move) median_first_ball_move,
               count(*) FILTER (WHERE winner = 'white') white_wins,
               count(*) FILTER (WHERE winner = 'black') black_wins,
               count(*) FILTER (WHERE winner IS NULL) draws
        FROM games
        """,
        [source],
    ).fetchone()
    if overview_row is None or int(overview_row[0]) == 0:
        raise ValueError("research input contains no games")
    move_row = connection.execute(
        """
        SELECT avg(policy_entropy), avg(legal_actions),
               count(*) FILTER (WHERE move_kind = 'replace'),
               count(*) FILTER (WHERE ball_moved),
               count(*) FILTER (WHERE unique_gradient),
               count(*) FILTER (WHERE reply_resistance = 0),
               count(*) FILTER (WHERE reply_resistance = 1),
               count(DISTINCT model_id)
        FROM read_parquet(?)
        """,
        [source],
    ).fetchone()
    assert move_row is not None

    opening_rows = connection.execute(
        """
        SELECT action, board_size, count(*) games
        FROM read_parquet(?) WHERE ply = 0
        GROUP BY action, board_size
        """,
        [source],
    ).fetchall()
    raw_openings: Counter[int] = Counter()
    canonical_openings: Counter[int] = Counter()
    for action, board_size, games in opening_rows:
        raw_openings[int(action)] += int(games)
        canonical_openings[_canonical_action(int(action), int(board_size))] += int(games)

    candidate_rows = connection.execute(
        """
        WITH values AS (
          SELECT *,
                 CASE WHEN turn = 'white' THEN root_value ELSE -root_value END white_value
          FROM read_parquet(?)
        ), changes AS (
          SELECT *, lag(white_value) OVER (PARTITION BY game_id ORDER BY ply) previous_value
          FROM values
        )
        SELECT game_id, ply, turn, action, move_kind, root_value, policy_entropy,
               reply_resistance,
               abs(white_value - previous_value) value_swing,
               candidate_actions[1] top_action,
               candidate_visits[1] top_visits,
               candidate_values[1] top_value
        FROM changes
        WHERE move_kind = 'replace'
           OR reply_resistance <= 1
           OR abs(white_value - previous_value) >= 0.5
        ORDER BY coalesce(reply_resistance, 999),
                 abs(white_value - previous_value) DESC NULLS LAST,
                 policy_entropy ASC
        LIMIT 100
        """,
        [source],
    ).fetchall()
    candidate_names = (
        "game_id",
        "ply",
        "turn",
        "action",
        "move_kind",
        "root_value",
        "policy_entropy",
        "reply_resistance",
        "value_swing",
        "top_action",
        "top_visits",
        "top_value",
    )
    candidates = [
        {name: value for name, value in zip(candidate_names, row, strict=True)}
        for row in candidate_rows
    ]
    result: dict[str, object] = {
        "schema_version": 1,
        "input": source,
        "overview": {
            "games": int(overview_row[0]),
            "moves": int(overview_row[1]),
            "mean_plies": float(overview_row[2]),
            "median_plies": float(overview_row[3]),
            "mean_first_ball_move": (
                float(overview_row[4]) if overview_row[4] is not None else None
            ),
            "median_first_ball_move": (
                float(overview_row[5]) if overview_row[5] is not None else None
            ),
            "white_wins": int(overview_row[6]),
            "black_wins": int(overview_row[7]),
            "draws": int(overview_row[8]),
        },
        "moves": {
            "mean_policy_entropy": float(move_row[0]),
            "mean_legal_actions": float(move_row[1]),
            "replacements": int(move_row[2]),
            "ball_moves": int(move_row[3]),
            "unique_gradients": int(move_row[4]),
            "reply_resistance_zero": int(move_row[5]),
            "reply_resistance_one": int(move_row[6]),
            "distinct_models": int(move_row[7]),
        },
        "openings": {
            "raw_distinct": len(raw_openings),
            "canonical_distinct": len(canonical_openings),
            "raw_entropy": _entropy(raw_openings),
            "canonical_entropy": _entropy(canonical_openings),
            "raw_counts": dict(raw_openings),
            "canonical_counts": dict(canonical_openings),
        },
        "tactical_candidates": candidates,
    }
    _atomic_json(output, result)
    return result
