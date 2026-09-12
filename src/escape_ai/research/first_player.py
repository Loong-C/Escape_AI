"""Matched-seed analysis for White-first and diagnostic Black-first games."""

from __future__ import annotations

import json
import math
import os
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import duckdb

from escape_ai import _escape_core

_AXIS_SWAPS = (
    _escape_core.Symmetry.ROTATE_90,
    _escape_core.Symmetry.ROTATE_270,
    _escape_core.Symmetry.DIAGONAL_MAIN,
    _escape_core.Symmetry.DIAGONAL_ANTI,
)


@dataclass(frozen=True, slots=True)
class TraceMove:
    state: bytes
    action: int


@dataclass(frozen=True, slots=True)
class GameTrace:
    game_id: str
    seed: int
    starting_player: str
    winner: str | None
    reason: str
    moves: tuple[TraceMove, ...]


def _atomic_json(path: Path, value: object) -> None:
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


def _load_traces(source: str) -> list[GameTrace]:
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            """
            SELECT game_id, seed, ply, turn, state, action, winner, reason
            FROM read_parquet(?) ORDER BY game_id, ply
            """,
            [source],
        ).fetchall()
    finally:
        connection.close()
    grouped: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[0])].append(row)
    traces: list[GameTrace] = []
    for game_id, game_rows in grouped.items():
        first = game_rows[0]
        if [int(row[2]) for row in game_rows] != list(range(len(game_rows))):
            raise ValueError(f"game {game_id} has non-contiguous plies")
        if any(row[6] != first[6] or row[7] != first[7] for row in game_rows):
            raise ValueError(f"game {game_id} has inconsistent outcome metadata")
        traces.append(
            GameTrace(
                game_id=game_id,
                seed=int(first[1]),
                starting_player=str(first[3]),
                winner=None if first[6] is None else str(first[6]),
                reason=str(first[7]),
                moves=tuple(
                    TraceMove(bytes(row[4]), int(row[5])) for row in game_rows
                ),
            )
        )
    return traces


def _mapped_player(player: str | None) -> str | None:
    if player is None:
        return None
    if player == "white":
        return "black"
    if player == "black":
        return "white"
    raise ValueError(f"invalid winner: {player}")


def _matching_symmetry_path(
    white: GameTrace,
    black: GameTrace,
) -> tuple[str, ...] | None:
    """Return a minimum-switch role-swapping symmetry for every recorded ply.

    A fixed transform is sufficient for generic positions.  At a position with
    a non-trivial D4 stabilizer, however, two equally valid representatives of
    the same action orbit can cause the fixed transform to change while both
    trajectories remain exactly equivalent in the quotient game.  Requiring
    one transform for the whole game would incorrectly reject that case.
    """

    if (
        len(white.moves) != len(black.moves)
        or _mapped_player(white.winner) != black.winner
        or white.reason != black.reason
    ):
        return None
    options: list[tuple[int, ...]] = []
    for source, target in zip(white.moves, black.moves, strict=True):
        state = _escape_core.State.deserialize(source.state)
        matching = tuple(
            index
            for index, symmetry in enumerate(_AXIS_SWAPS)
            if state.transformed(symmetry).serialize() == target.state
            and _escape_core.transform_action(source.action, state.size, symmetry)
            == target.action
        )
        if not matching:
            return None
        options.append(matching)

    # Dynamic programming avoids introducing an unnecessary switch when an
    # early symmetric position admits several equally valid representatives.
    paths: dict[int, tuple[int, tuple[int, ...]]] = {
        symmetry: (0, (symmetry,)) for symmetry in options[0]
    }
    for matching in options[1:]:
        updated: dict[int, tuple[int, tuple[int, ...]]] = {}
        for symmetry in matching:
            updated[symmetry] = min(
                (
                    switches + int(previous != symmetry),
                    (*path, symmetry),
                )
                for previous, (switches, path) in paths.items()
            )
        paths = updated
    _switches, selected = min(paths.values())
    return tuple(_AXIS_SWAPS[index].name.lower() for index in selected)


def _symmetry_segments(path: tuple[str, ...]) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    previous: str | None = None
    for ply, symmetry in enumerate(path):
        if symmetry != previous:
            segments.append({"ply": ply, "symmetry": symmetry})
            previous = symmetry
    return segments


def _outcome_summary(traces: list[GameTrace]) -> dict[str, object]:
    wins = Counter(trace.winner for trace in traces)
    first_wins = sum(trace.winner == trace.starting_player for trace in traces)
    second_wins = sum(
        trace.winner is not None and trace.winner != trace.starting_player
        for trace in traces
    )
    draws = wins[None]
    return {
        "games": len(traces),
        "white_wins": wins["white"],
        "black_wins": wins["black"],
        "draws": draws,
        "first_player_wins": first_wins,
        "second_player_wins": second_wins,
        "first_player_score": (
            (first_wins + 0.5 * draws) / len(traces) if traces else None
        ),
        "mean_plies": (
            sum(len(trace.moves) for trace in traces) / len(traces) if traces else None
        ),
    }


def _wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> list[float]:
    if trials == 0:
        return [0.0, 1.0]
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return [center - radius, center + radius]


def _exact_binomial_p(successes: int, trials: int) -> float:
    if trials == 0:
        return 1.0
    tail = min(successes, trials - successes)
    probability = float(
        sum(math.comb(trials, value) for value in range(tail + 1)) / 2**trials
    )
    return min(1.0, 2.0 * probability)


def analyze_first_player_games(source: str, output: Path) -> dict[str, object]:
    """Validate paired role-swapped traces and estimate first-player advantage."""

    traces = _load_traces(source)
    if not traces:
        raise ValueError("first-player analysis requires at least one game")
    by_seed: dict[int, list[GameTrace]] = defaultdict(list)
    for trace in traces:
        by_seed[trace.seed].append(trace)
    invalid_pairs: list[dict[str, object]] = []
    symmetry_counts: Counter[str] = Counter()
    symmetry_step_counts: Counter[str] = Counter()
    dynamic_pairs: list[dict[str, object]] = []
    white_first: list[GameTrace] = []
    black_first: list[GameTrace] = []
    for seed, pair in sorted(by_seed.items()):
        by_start = {trace.starting_player: trace for trace in pair}
        if len(pair) != 2 or set(by_start) != {"white", "black"}:
            invalid_pairs.append(
                {"seed": seed, "game_ids": [trace.game_id for trace in pair]}
            )
            continue
        white = by_start["white"]
        black = by_start["black"]
        white_first.append(white)
        black_first.append(black)
        symmetry_path = _matching_symmetry_path(white, black)
        if symmetry_path is None:
            invalid_pairs.append(
                {"seed": seed, "game_ids": [white.game_id, black.game_id]}
            )
        else:
            segments = _symmetry_segments(symmetry_path)
            symmetry_step_counts.update(symmetry_path)
            if len(segments) == 1:
                symmetry_counts[symmetry_path[0]] += 1
            else:
                symmetry_counts["dynamic"] += 1
                dynamic_pairs.append(
                    {
                        "seed": seed,
                        "game_ids": [white.game_id, black.game_id],
                        "symmetry_segments": segments,
                    }
                )

    official = _outcome_summary(white_first)
    diagnostic = _outcome_summary(black_first)
    decisive = cast(int, official["first_player_wins"]) + cast(
        int, official["second_player_wins"]
    )
    first_wins = cast(int, official["first_player_wins"])
    result: dict[str, object] = {
        "source": source,
        "games": len(traces),
        "matched_seeds": len(by_seed),
        "mirrored_pairs": sum(symmetry_counts.values()),
        "all_pairs_mirrored": not invalid_pairs and len(by_seed) == len(white_first),
        "symmetry_counts": dict(sorted(symmetry_counts.items())),
        "symmetry_step_counts": dict(sorted(symmetry_step_counts.items())),
        "dynamic_symmetry_pairs": len(dynamic_pairs),
        "symmetry_switches": sum(
            len(cast(list[object], pair["symmetry_segments"])) - 1
            for pair in dynamic_pairs
        ),
        "dynamic_pairs": dynamic_pairs,
        "invalid_pairs": invalid_pairs,
        "official_white_first": official,
        "diagnostic_black_first": diagnostic,
        "first_player_inference": {
            "independent_games": len(white_first),
            "decisive_games": decisive,
            "first_player_wins": first_wins,
            "decisive_win_rate": first_wins / decisive if decisive else None,
            "wilson_95": _wilson_interval(first_wins, decisive),
            "two_sided_exact_binomial_p_vs_half": _exact_binomial_p(
                first_wins, decisive
            ),
            "note": "Black-first games are mirrored validation pairs, not independent samples.",
        },
    }
    _atomic_json(output, result)
    if invalid_pairs:
        raise RuntimeError(
            f"{len(invalid_pairs)} first-player pairs failed structural or D4 validation"
        )
    return result
