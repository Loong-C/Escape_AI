from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from escape_ai import _escape_core
from escape_ai.search import (
    D4_SYMMETRIES,
    D4CanonicalEvaluator,
    D4SymmetryEnsembleEvaluator,
    Evaluation,
)


class CoordinateSensitiveEvaluator:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def evaluate(self, states: Sequence[_escape_core.State]) -> list[Evaluation]:
        self.batch_sizes.append(len(states))
        results: list[Evaluation] = []
        for state in states:
            action_space = (state.size + 1) ** 2
            legal = np.asarray(state.legal_actions(), dtype=np.int64)
            weights = np.zeros(action_space, dtype=np.float32)
            weights[legal] = (legal + 1).astype(np.float32)
            weights /= weights.sum()
            signed_posts = sum(
                (index + 1) * (1 if post == "white" else -1)
                for index, post in enumerate(state.posts)
                if post is not None
            )
            ball_row, ball_col = state.ball
            turn_bias = 17 if state.turn == "white" else -11
            value = float(np.tanh((signed_posts + 3 * ball_row - 5 * ball_col + turn_bias) / 50))
            results.append(Evaluation(weights, value))
        return results


def _asymmetric_state() -> _escape_core.State:
    state = _escape_core.State(5)
    for action in (0, 8, 15, 5, 23, 31, 2):
        state = state.apply(action)
    return state


def _map_to_source(
    state: _escape_core.State,
    transformed: Evaluation,
    symmetry: _escape_core.Symmetry,
) -> np.ndarray:
    policy = np.zeros_like(transformed.priors)
    for action in state.legal_actions():
        policy[action] = transformed.priors[
            _escape_core.transform_action(action, state.size, symmetry)
        ]
    return policy


def test_d4_ensemble_is_equivariant_and_deduplicates_one_orbit() -> None:
    state = _asymmetric_state()
    raw = CoordinateSensitiveEvaluator()
    ensemble = D4SymmetryEnsembleEvaluator(raw, maximum_batch_size=3)
    transformed_states = [state.transformed(symmetry) for symmetry in D4_SYMMETRIES]

    evaluations = ensemble.evaluate(transformed_states)

    assert raw.batch_sizes == [3, 3, 2]
    base = evaluations[0]
    for symmetry, evaluation in zip(D4_SYMMETRIES, evaluations, strict=True):
        assert evaluation.value == base.value
        np.testing.assert_array_equal(
            _map_to_source(state, evaluation, symmetry),
            base.priors,
        )


def test_d4_ensemble_returns_normalized_legal_policy() -> None:
    state = _asymmetric_state()
    ensemble = D4SymmetryEnsembleEvaluator(
        CoordinateSensitiveEvaluator(), maximum_batch_size=8
    )

    evaluation = ensemble.evaluate([state])[0]

    legal = np.asarray(state.legal_actions(), dtype=np.int64)
    illegal = np.ones_like(evaluation.priors, dtype=np.bool_)
    illegal[legal] = False
    assert np.isclose(evaluation.priors[legal].sum(), 1.0)
    assert np.count_nonzero(evaluation.priors[illegal]) == 0
    assert -1.0 <= evaluation.value <= 1.0


def test_d4_ensemble_accepts_an_empty_batch() -> None:
    raw = CoordinateSensitiveEvaluator()
    ensemble = D4SymmetryEnsembleEvaluator(raw)

    assert ensemble.evaluate([]) == []
    assert raw.batch_sizes == []


def test_d4_canonical_evaluator_is_equivariant_with_one_network_view() -> None:
    state = _asymmetric_state()
    raw = CoordinateSensitiveEvaluator()
    evaluator = D4CanonicalEvaluator(raw, maximum_batch_size=3)
    transformed_states = [state.transformed(symmetry) for symmetry in D4_SYMMETRIES]

    evaluations = evaluator.evaluate(transformed_states)

    assert raw.batch_sizes == [1]
    base = evaluations[0]
    for symmetry, evaluation in zip(D4_SYMMETRIES, evaluations, strict=True):
        assert evaluation.value == base.value
        np.testing.assert_array_equal(
            _map_to_source(state, evaluation, symmetry),
            base.priors,
        )


def test_d4_canonical_evaluator_stabilizes_symmetric_states() -> None:
    state = _escape_core.State(5)
    raw = CoordinateSensitiveEvaluator()
    evaluator = D4CanonicalEvaluator(raw)

    evaluations = evaluator.evaluate(
        [state.transformed(symmetry) for symmetry in D4_SYMMETRIES]
    )

    assert raw.batch_sizes == [1]
    base = evaluations[0]
    legal = np.asarray(state.legal_actions(), dtype=np.int64)
    assert np.isclose(base.priors[legal].sum(), 1.0)
    for symmetry, evaluation in zip(D4_SYMMETRIES, evaluations, strict=True):
        assert evaluation.value == base.value
        np.testing.assert_array_equal(
            _map_to_source(state, evaluation, symmetry),
            base.priors,
        )


def test_d4_canonical_evaluator_chunks_distinct_orbits() -> None:
    first = _asymmetric_state()
    second = first.apply(first.legal_actions()[0])
    raw = CoordinateSensitiveEvaluator()
    evaluator = D4CanonicalEvaluator(raw, maximum_batch_size=1)

    results = evaluator.evaluate([first, second])

    assert len(results) == 2
    assert raw.batch_sizes == [1, 1]


def test_d4_canonical_evaluator_accepts_an_empty_batch() -> None:
    raw = CoordinateSensitiveEvaluator()
    evaluator = D4CanonicalEvaluator(raw)

    assert evaluator.evaluate([]) == []
    assert raw.batch_sizes == []
