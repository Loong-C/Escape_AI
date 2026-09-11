"""DuckDB summaries and tactical candidate mining for research games."""

from __future__ import annotations

import json
import math
import os
import statistics
import uuid
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import duckdb

from escape_ai import _escape_core

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
_OPENING_DEPTHS = (1, 3, 5, 10, 20)


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


def _entropy[CounterKey](counts: Mapping[CounterKey, int]) -> float:
    total = sum(counts.values())
    return -sum((count / total) * math.log(count / total) for count in counts.values() if count)


def _canonical_action(action: int, size: int) -> int:
    return min(_escape_core.transform_action(action, size, symmetry) for symmetry in _SYMMETRIES)


def _canonical_sequence(actions: tuple[int, ...], size: int) -> tuple[int, ...]:
    return min(
        tuple(_escape_core.transform_action(action, size, symmetry) for action in actions)
        for symmetry in _SYMMETRIES
    )


def _distribution(values: list[int]) -> dict[str, object]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "minimum": None, "maximum": None}
    counts = Counter(values)
    return {
        "count": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
        "counts": dict(sorted(counts.items())),
    }


def _opening_prefix_summary(
    games: list[tuple[int, tuple[int, ...]]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for depth in _OPENING_DEPTHS:
        raw: Counter[tuple[int, ...]] = Counter()
        canonical: Counter[tuple[int, ...]] = Counter()
        for size, actions in games:
            if len(actions) < depth:
                continue
            prefix = actions[:depth]
            raw[prefix] += 1
            canonical[_canonical_sequence(prefix, size)] += 1
        result[str(depth)] = {
            "games": sum(raw.values()),
            "raw_distinct": len(raw),
            "canonical_distinct": len(canonical),
            "raw_entropy": _entropy(raw),
            "canonical_entropy": _entropy(canonical),
            "top_canonical": [
                {"actions": list(actions), "games": count}
                for actions, count in canonical.most_common(20)
            ],
        }
    return result


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

    game_rows = connection.execute(
        """
        SELECT game_id, any_value(board_size) board_size,
               list(action ORDER BY ply) actions,
               any_value(winner) winner, any_value(reason) reason,
               min(ply) FILTER (WHERE ball_moved) first_ball_move,
               count(*) FILTER (WHERE ball_moved) ball_moves,
               count(*) FILTER (WHERE move_kind = 'replace') replacements
        FROM read_parquet(?)
        GROUP BY game_id ORDER BY game_id
        """,
        [source],
    ).fetchall()
    opening_games = [
        (int(row[1]), tuple(int(action) for action in row[2])) for row in game_rows
    ]
    first_ball_moves = [int(row[5]) + 1 for row in game_rows if row[5] is not None]
    ball_moves_per_game = [int(row[6]) for row in game_rows]
    replacements_per_game = [int(row[7]) for row in game_rows]
    termination_reasons = Counter(str(row[4]) for row in game_rows)

    phase_rows = connection.execute(
        """
        SELECT CASE WHEN ply < 20 THEN 'opening'
                    WHEN ply < 80 THEN 'middlegame'
                    ELSE 'late' END phase,
               count(*) moves, avg(policy_entropy) mean_policy_entropy,
               avg(legal_actions) mean_legal_actions,
               avg(abs(root_value)) mean_absolute_root_value,
               count(*) FILTER (WHERE move_kind = 'replace') replacements,
               count(*) FILTER (WHERE ball_moved) ball_moves,
               count(*) FILTER (WHERE reply_resistance <= 1) forcing_moves
        FROM read_parquet(?) GROUP BY phase
        """,
        [source],
    ).fetchall()
    phase_names = (
        "phase",
        "moves",
        "mean_policy_entropy",
        "mean_legal_actions",
        "mean_absolute_root_value",
        "replacements",
        "ball_moves",
        "forcing_moves",
    )
    phases = {
        str(row[0]): {name: value for name, value in zip(phase_names[1:], row[1:], strict=True)}
        for row in phase_rows
    }

    first_move_structure = connection.execute(
        """
        WITH moved AS (
          SELECT *, row_number() OVER (PARTITION BY game_id ORDER BY ply) move_rank
          FROM read_parquet(?) WHERE ball_moved
        )
        SELECT count(*), avg(ply + 1),
               avg(white_floating + black_floating),
               avg(white_anchored + black_anchored),
               avg(white_walls + black_walls),
               avg(legal_actions)
        FROM moved WHERE move_rank = 1
        """,
        [source],
    ).fetchone()
    assert first_move_structure is not None

    direction_rows = connection.execute(
        """
        SELECT ball_move_direction, count(*)
        FROM read_parquet(?) WHERE ball_moved
        GROUP BY ball_move_direction ORDER BY ball_move_direction
        """,
        [source],
    ).fetchall()
    ball_move_directions = {str(direction): int(count) for direction, count in direction_rows}

    matchup_rows = connection.execute(
        """
        SELECT white_model_id, black_model_id, count(DISTINCT game_id),
               count(DISTINCT game_id) FILTER (WHERE winner = 'white'),
               count(DISTINCT game_id) FILTER (WHERE winner = 'black'),
               count(DISTINCT game_id) FILTER (WHERE winner IS NULL)
        FROM read_parquet(?) GROUP BY white_model_id, black_model_id
        ORDER BY white_model_id, black_model_id
        """,
        [source],
    ).fetchall()
    model_matchups = [
        {
            "white_model_id": str(row[0]),
            "black_model_id": str(row[1]),
            "games": int(row[2]),
            "white_wins": int(row[3]),
            "black_wins": int(row[4]),
            "draws": int(row[5]),
        }
        for row in matchup_rows
    ]

    candidate_value_rows = connection.execute(
        """
        SELECT candidate_values
        FROM read_parquet(?) WHERE len(candidate_values) >= 2
        """,
        [source],
    ).fetchall()
    candidate_value_gaps = [
        abs(float(row[0][0]) - float(row[0][1])) for row in candidate_value_rows
    ]
    candidate_gap_summary: dict[str, object] = {
        "positions": len(candidate_value_gaps),
        "mean": statistics.mean(candidate_value_gaps) if candidate_value_gaps else None,
        "median": statistics.median(candidate_value_gaps) if candidate_value_gaps else None,
        "at_least_0_25": sum(value >= 0.25 for value in candidate_value_gaps),
        "at_least_0_50": sum(value >= 0.50 for value in candidate_value_gaps),
    }

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
            "termination_reasons": dict(termination_reasons),
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
            "ball_move_directions": ball_move_directions,
            "ball_moves_per_game": _distribution(ball_moves_per_game),
            "replacements_per_game": _distribution(replacements_per_game),
        },
        "openings": {
            "raw_distinct": len(raw_openings),
            "canonical_distinct": len(canonical_openings),
            "raw_entropy": _entropy(raw_openings),
            "canonical_entropy": _entropy(canonical_openings),
            "raw_counts": dict(raw_openings),
            "canonical_counts": dict(canonical_openings),
            "prefixes": _opening_prefix_summary(opening_games),
        },
        "first_ball_move": {
            "ply_distribution": _distribution(first_ball_moves),
            "games_without_movement": len(game_rows) - len(first_ball_moves),
            "structure": {
                "games": int(first_move_structure[0]),
                "mean_ply": (
                    float(first_move_structure[1])
                    if first_move_structure[1] is not None
                    else None
                ),
                "mean_floating_posts": (
                    float(first_move_structure[2])
                    if first_move_structure[2] is not None
                    else None
                ),
                "mean_anchored_posts": (
                    float(first_move_structure[3])
                    if first_move_structure[3] is not None
                    else None
                ),
                "mean_walls": (
                    float(first_move_structure[4])
                    if first_move_structure[4] is not None
                    else None
                ),
                "mean_legal_actions": (
                    float(first_move_structure[5])
                    if first_move_structure[5] is not None
                    else None
                ),
            },
        },
        "phases": phases,
        "model_matchups": model_matchups,
        "candidate_value_gaps": candidate_gap_summary,
        "tactical_candidates": candidates,
    }
    _atomic_json(output, result)
    return result
