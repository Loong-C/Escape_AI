"""Matched-color strength analysis for two checkpoint evaluators."""

from __future__ import annotations

import json
import math
import os
import statistics
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb


@dataclass(frozen=True, slots=True)
class MatchGame:
    game_id: str
    seed: int
    starting_player: str
    white_agent: str
    black_agent: str
    winner: str | None
    reason: str
    plies: int


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


def _load_games(source: str) -> list[MatchGame]:
    input_path = Path(source)
    selected = str(input_path / "*.parquet") if input_path.is_dir() else source
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            """
            SELECT game_id, any_value(seed), arg_min(turn, ply),
                   any_value(white_model_id), any_value(black_model_id),
                   any_value(winner), any_value(reason), max(ply) + 1,
                   count(*), count(DISTINCT ply), min(ply),
                   count(DISTINCT seed), count(DISTINCT white_model_id),
                   count(DISTINCT black_model_id), count(DISTINCT reason),
                   count(DISTINCT coalesce(winner, '__draw__'))
            FROM read_parquet(?)
            GROUP BY game_id ORDER BY game_id
            """,
            [selected],
        ).fetchall()
    finally:
        connection.close()

    games: list[MatchGame] = []
    for row in rows:
        moves = int(row[8])
        if (
            int(row[9]) != moves
            or int(row[10]) != 0
            or int(row[7]) != moves
            or any(int(row[index]) != 1 for index in range(11, 16))
        ):
            raise ValueError(f"game {row[0]} has inconsistent rows or metadata")
        games.append(
            MatchGame(
                game_id=str(row[0]),
                seed=int(row[1]),
                starting_player=str(row[2]),
                white_agent=str(row[3]),
                black_agent=str(row[4]),
                winner=None if row[5] is None else str(row[5]),
                reason=str(row[6]),
                plies=moves,
            )
        )
    return games


def _score(game: MatchGame, agent: str) -> float:
    if game.winner is None:
        return 0.5
    if game.winner not in {"white", "black"}:
        raise ValueError(f"game {game.game_id} has invalid winner {game.winner!r}")
    winner_agent = game.white_agent if game.winner == "white" else game.black_agent
    return float(winner_agent == agent)


def _wilson_interval(successes: int, trials: int) -> list[float]:
    if trials == 0:
        return [0.0, 1.0]
    z = 1.959963984540054
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


def _clustered_interval(scores: list[float]) -> list[float]:
    if len(scores) < 2:
        return [0.0, 1.0]
    radius = 1.959963984540054 * statistics.stdev(scores) / math.sqrt(len(scores))
    mean = statistics.fmean(scores)
    return [max(0.0, mean - radius), min(1.0, mean + radius)]


def _classification(interval: list[float]) -> str:
    if interval[0] > 0.5:
        return "d4-superior"
    if interval[1] < 0.45:
        return "d4-materially-inferior"
    if interval[0] >= 0.45:
        return "d4-noninferior"
    return "inconclusive"


def analyze_evaluator_match(source: str, output: Path) -> dict[str, object]:
    """Validate paired color swaps and compare evaluator strength by seed cluster."""

    games = _load_games(source)
    if not games:
        raise ValueError("evaluator-match analysis requires at least one game")
    agents = sorted({game.white_agent for game in games} | {game.black_agent for game in games})
    if len(agents) != 2:
        raise ValueError("evaluator-match analysis requires exactly two agent IDs")
    raw_agents = [agent for agent in agents if agent.endswith("-raw")]
    d4_agents = [agent for agent in agents if agent.endswith("-d4")]
    if len(raw_agents) != 1 or len(d4_agents) != 1:
        raise ValueError("expected exactly one -raw and one -d4 agent ID")
    raw_agent = raw_agents[0]
    d4_agent = d4_agents[0]

    by_seed: dict[int, list[MatchGame]] = defaultdict(list)
    for game in games:
        by_seed[game.seed].append(game)
    invalid_pairs: list[dict[str, Any]] = []
    valid_pairs: list[list[MatchGame]] = []
    expected_assignments = {(raw_agent, d4_agent), (d4_agent, raw_agent)}
    for seed, pair in sorted(by_seed.items()):
        assignments = {(game.white_agent, game.black_agent) for game in pair}
        if (
            len(pair) != 2
            or assignments != expected_assignments
            or any(game.starting_player != "white" for game in pair)
        ):
            invalid_pairs.append(
                {
                    "seed": seed,
                    "game_ids": [game.game_id for game in pair],
                    "assignments": [
                        [game.white_agent, game.black_agent] for game in pair
                    ],
                }
            )
        else:
            valid_pairs.append(pair)

    color_summary: dict[str, dict[str, object]] = {}
    for agent in (raw_agent, d4_agent):
        by_color: dict[str, object] = {}
        for color in ("white", "black"):
            selected = [
                game
                for game in games
                if (game.white_agent if color == "white" else game.black_agent) == agent
            ]
            score = sum(_score(game, agent) for game in selected)
            by_color[color] = {
                "games": len(selected),
                "wins": sum(_score(game, agent) == 1.0 for game in selected),
                "draws": sum(game.winner is None for game in selected),
                "losses": sum(_score(game, agent) == 0.0 for game in selected),
                "score": score / len(selected) if selected else None,
            }
        color_summary[agent] = by_color

    d4_game_scores = [_score(game, d4_agent) for game in games]
    d4_wins = sum(score == 1.0 for score in d4_game_scores)
    d4_losses = sum(score == 0.0 for score in d4_game_scores)
    draws = len(games) - d4_wins - d4_losses
    pair_scores = [sum(_score(game, d4_agent) for game in pair) / 2.0 for pair in valid_pairs]
    pair_wins = sum(score > 0.5 for score in pair_scores)
    pair_losses = sum(score < 0.5 for score in pair_scores)
    pair_ties = len(pair_scores) - pair_wins - pair_losses
    interval = _clustered_interval(pair_scores)
    point_counts = Counter(f"{score:.2f}" for score in pair_scores)

    result: dict[str, object] = {
        "source": source,
        "games": len(games),
        "matched_seeds": len(by_seed),
        "valid_pairs": len(valid_pairs),
        "all_pairs_valid": not invalid_pairs and len(valid_pairs) == len(by_seed),
        "invalid_pairs": invalid_pairs,
        "raw_agent_id": raw_agent,
        "d4_agent_id": d4_agent,
        "color_summary": color_summary,
        "overall": {
            "d4_wins": d4_wins,
            "raw_wins": d4_losses,
            "draws": draws,
            "d4_score": sum(d4_game_scores) / len(games),
            "decisive_d4_win_rate": (
                d4_wins / (d4_wins + d4_losses) if d4_wins + d4_losses else None
            ),
            "decisive_wilson_95": _wilson_interval(d4_wins, d4_wins + d4_losses),
            "individual_game_exact_binomial_p_vs_half": _exact_binomial_p(
                d4_wins, d4_wins + d4_losses
            ),
        },
        "paired_inference": {
            "independent_seed_clusters": len(pair_scores),
            "d4_mean_score": statistics.fmean(pair_scores),
            "clustered_normal_95": interval,
            "d4_pair_wins": pair_wins,
            "raw_pair_wins": pair_losses,
            "tied_pairs": pair_ties,
            "pair_score_counts": dict(sorted(point_counts.items())),
            "two_sided_exact_sign_p": _exact_binomial_p(
                pair_wins, pair_wins + pair_losses
            ),
            "noninferiority_margin": 0.05,
            "classification": _classification(interval),
            "note": "The paired-seed cluster, not each game, is the primary unit.",
        },
    }
    _atomic_json(output, result)
    if invalid_pairs:
        raise RuntimeError(f"{len(invalid_pairs)} evaluator pairs failed validation")
    return result
