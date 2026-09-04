from __future__ import annotations

import random

import numpy as np
import pytest

pyspiel = pytest.importorskip("pyspiel")

from open_spiel.python.algorithms import mcts  # noqa: E402

from escape_ai import _escape_core  # noqa: E402
from escape_ai.integrations.openspiel import load_game  # noqa: E402


def test_registered_game_passes_openspiel_random_simulation_test() -> None:
    game = load_game(3)
    pyspiel.random_sim_test(game, num_sims=20, serialize=False, verbose=False)


def test_openspiel_transitions_match_the_cpp_engine() -> None:
    game = load_game(5)
    spiel_state = game.new_initial_state()
    core_state = _escape_core.State(5)
    rng = random.Random(20260904)

    while not spiel_state.is_terminal():
        assert spiel_state.current_player() == (0 if core_state.turn == "white" else 1)
        assert spiel_state.legal_actions() == core_state.legal_actions()
        assert spiel_state.core_state.serialize() == core_state.serialize()
        action = rng.choice(core_state.legal_actions())
        spiel_state.apply_action(action)
        core_state = core_state.apply(action)

    assert spiel_state.core_state.serialize() == core_state.serialize()
    winner = core_state.outcome["winner"]
    expected = [0.0, 0.0]
    if winner == "white":
        expected = [1.0, -1.0]
    elif winner == "black":
        expected = [-1.0, 1.0]
    assert spiel_state.returns() == expected


def test_cloned_state_is_independent() -> None:
    state = load_game(3).new_initial_state()
    clone = state.clone()
    clone.apply_action(clone.legal_actions()[0])
    assert state.move_number() == 0
    assert clone.move_number() == 1
    assert state.core_state.serialize() != clone.core_state.serialize()


def test_openspiel_mcts_can_search_the_adapter() -> None:
    game = load_game(3)
    state = game.new_initial_state()
    numpy_rng = np.random.RandomState(7)
    evaluator = mcts.RandomRolloutEvaluator(n_rollouts=2, random_state=numpy_rng)
    bot = mcts.MCTSBot(
        game,
        uct_c=1.4,
        max_simulations=40,
        evaluator=evaluator,
        solve=True,
        random_state=numpy_rng,
    )
    action = bot.step(state)
    assert action in state.legal_actions()
