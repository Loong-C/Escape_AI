from __future__ import annotations

import random

import pytest

from escape_ai import _escape_core
from escape_ai.search import (
    Agent,
    GreedyAgent,
    HeuristicAgent,
    PureMCTSAgent,
    RandomAgent,
    play_game,
    run_match,
    solve_exact,
)


def trapping_position() -> _escape_core.State:
    state = _escape_core.State(3)
    state.set_post(1, 1, "white")
    state.set_post(1, 2, "white")
    state.set_post(2, 1, "white")
    return state


@pytest.mark.parametrize(
    "agent",
    [GreedyAgent(), HeuristicAgent(depth=1), PureMCTSAgent(simulations=40)],
)
def test_baselines_take_an_immediate_trapping_win(agent: Agent) -> None:
    state = trapping_position()
    action = agent.select_action(state, random.Random(7))
    child = state.apply(action)
    assert child.outcome["winner"] == "white"
    assert child.outcome["reason"] == "trapped"


def test_oracle_proves_the_immediate_trapping_win() -> None:
    state = trapping_position()
    result = solve_exact(state, time_limit_seconds=5, maximum_nodes=100_000)
    assert result.value == 1
    assert 2 * 4 + 2 in result.best_actions


def test_seeded_random_game_is_reproducible() -> None:
    first = play_game(RandomAgent(), RandomAgent(), size=3, seed=11)
    second = play_game(RandomAgent(), RandomAgent(), size=3, seed=11)
    assert first == second


def test_match_swaps_colors_and_accounts_for_every_game() -> None:
    result = run_match(RandomAgent(), GreedyAgent(), games=4, size=3, seed=17)
    assert result.games == 4
    assert result.first_wins + result.second_wins + result.draws == 4
    assert result.total_plies > 0
