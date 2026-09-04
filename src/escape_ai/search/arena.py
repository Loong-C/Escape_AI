"""Deterministic paired matches for fixed agents."""

from __future__ import annotations

import random
from dataclasses import dataclass

from escape_ai import _escape_core

from .agents import Agent


@dataclass(frozen=True, slots=True)
class PlayedGame:
    winner: str | None
    reason: str
    plies: int
    actions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MatchResult:
    first_agent: str
    second_agent: str
    games: int
    first_wins: int
    second_wins: int
    draws: int
    total_plies: int


def play_game(
    white: Agent,
    black: Agent,
    *,
    size: int,
    seed: int,
) -> PlayedGame:
    state = _escape_core.State(size)
    rng = random.Random(seed)
    actions: list[int] = []
    while state.outcome["status"] == "playing":
        agent = white if state.turn == "white" else black
        action = agent.select_action(state, rng)
        if action not in state.legal_actions():
            raise AssertionError(f"{agent.name} selected illegal action {action}")
        actions.append(action)
        state = state.apply(action)
    return PlayedGame(
        winner=state.outcome["winner"],
        reason=str(state.outcome["reason"]),
        plies=state.ply,
        actions=tuple(actions),
    )


def run_match(
    first: Agent,
    second: Agent,
    *,
    games: int,
    size: int,
    seed: int,
) -> MatchResult:
    first_wins = 0
    second_wins = 0
    draws = 0
    total_plies = 0
    for game_index in range(games):
        first_is_white = game_index % 2 == 0
        white = first if first_is_white else second
        black = second if first_is_white else first
        game = play_game(white, black, size=size, seed=seed + game_index // 2)
        total_plies += game.plies
        if game.winner is None:
            draws += 1
        elif (game.winner == "white") == first_is_white:
            first_wins += 1
        else:
            second_wins += 1
    return MatchResult(
        first.name,
        second.name,
        games,
        first_wins,
        second_wins,
        draws,
        total_plies,
    )
