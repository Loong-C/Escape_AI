"""Color-paired cross-play matrices with uncertainty estimates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

from escape_ai.search.agents import Agent
from escape_ai.search.arena import MatchResult, run_match


@dataclass(frozen=True, slots=True)
class LeagueEntry:
    agent_id: str
    agent: Agent


@dataclass(frozen=True, slots=True)
class ScoredMatch:
    first_agent: str
    second_agent: str
    games: int
    first_wins: int
    second_wins: int
    draws: int
    total_plies: int
    first_score: float
    confidence_low: float
    confidence_high: float


@dataclass(frozen=True, slots=True)
class LeagueResult:
    board_size: int
    games_per_matchup: int
    seed: int
    matches: tuple[ScoredMatch, ...]


def _score_match(result: MatchResult) -> ScoredMatch:
    score = (result.first_wins + 0.5 * result.draws) / result.games
    z = 1.959963984540054
    denominator = 1.0 + z**2 / result.games
    center = (score + z**2 / (2 * result.games)) / denominator
    margin = (
        z
        * math.sqrt(score * (1.0 - score) / result.games + z**2 / (4 * result.games**2))
        / denominator
    )
    return ScoredMatch(
        first_agent=result.first_agent,
        second_agent=result.second_agent,
        games=result.games,
        first_wins=result.first_wins,
        second_wins=result.second_wins,
        draws=result.draws,
        total_plies=result.total_plies,
        first_score=score,
        confidence_low=max(0.0, center - margin),
        confidence_high=min(1.0, center + margin),
    )


def run_league(
    entries: list[LeagueEntry],
    *,
    games_per_matchup: int,
    board_size: int,
    seed: int,
) -> LeagueResult:
    if games_per_matchup < 2 or games_per_matchup % 2 != 0:
        raise ValueError("league matchups require a positive even game count")
    if len({entry.agent_id for entry in entries}) != len(entries):
        raise ValueError("league agent IDs must be unique")
    matches = tuple(
        _score_match(
            run_match(
                first.agent,
                second.agent,
                games=games_per_matchup,
                size=board_size,
                seed=seed + match_index * 1_000_000,
            )
        )
        for match_index, (first, second) in enumerate(combinations(entries, 2))
    )
    return LeagueResult(board_size, games_per_matchup, seed, matches)


def should_promote(match: ScoredMatch, *, threshold: float = 0.5) -> bool:
    """Promote the first agent only when its 95% interval clears the threshold."""

    return match.confidence_low > threshold
