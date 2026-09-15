"""Role-aware D4 ensemble evaluation for Escape positions."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from escape_ai import _escape_core

from .d4 import D4_SYMMETRIES
from .puct import Evaluation, PositionEvaluator


@dataclass(frozen=True, slots=True)
class _CanonicalPosition:
    key: bytes
    state: _escape_core.State
    source_to_canonical: _escape_core.Symmetry


def _canonical_position(state: _escape_core.State) -> _CanonicalPosition:
    if state.outcome["status"] != "playing":
        raise ValueError("symmetry ensemble requires playing states")
    candidates = [
        (transformed.serialize(), index, symmetry, transformed)
        for index, symmetry in enumerate(D4_SYMMETRIES)
        for transformed in (state.transformed(symmetry),)
    ]
    key, _index, symmetry, canonical = min(candidates, key=lambda item: (item[0], item[1]))
    return _CanonicalPosition(key, canonical, symmetry)


def _map_policy_to_source(
    source: _escape_core.State,
    transformed_policy: np.ndarray[tuple[int], np.dtype[np.float32]],
    source_to_transformed: _escape_core.Symmetry,
) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
    mapped = np.zeros((source.size + 1) ** 2, dtype=np.float32)
    for action in source.legal_actions():
        transformed_action = _escape_core.transform_action(
            action, source.size, source_to_transformed
        )
        mapped[action] = transformed_policy[transformed_action]
    return mapped


def _normalized_legal_policy(
    state: _escape_core.State,
    policy: np.ndarray[tuple[int], np.dtype[np.float32]],
) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
    expected_shape = ((state.size + 1) ** 2,)
    if policy.shape != expected_shape:
        raise ValueError("base evaluator policy has the wrong action-space shape")
    legal = np.asarray(state.legal_actions(), dtype=np.int64)
    normalized = np.zeros(expected_shape, dtype=np.float32)
    legal_weights = np.maximum(policy[legal].astype(np.float64), 0.0)
    total = float(legal_weights.sum())
    if not math.isfinite(total) or total <= 0.0:
        legal_weights.fill(1.0 / len(legal))
    else:
        legal_weights /= total
    normalized[legal] = legal_weights.astype(np.float32)
    return normalized


def _stabilize_canonical_policy(
    canonical: _escape_core.State,
    policy: np.ndarray[tuple[int], np.dtype[np.float32]],
) -> np.ndarray[tuple[int], np.dtype[np.float32]]:
    """Make one canonical policy exactly invariant under its state stabilizer."""

    key = canonical.serialize()
    stabilizers = tuple(
        symmetry
        for symmetry in D4_SYMMETRIES
        if canonical.transformed(symmetry).serialize() == key
    )
    stabilized = np.zeros_like(policy)
    remaining = set(canonical.legal_actions())
    while remaining:
        representative = min(remaining)
        orbit = sorted(
            {
                _escape_core.transform_action(representative, canonical.size, symmetry)
                for symmetry in stabilizers
            }
        )
        mean = float(sum(float(policy[action]) for action in orbit) / len(orbit))
        stabilized[orbit] = mean
        remaining.difference_update(orbit)
    return _normalized_legal_policy(canonical, stabilized)


class D4CanonicalEvaluator:
    """Evaluate one canonical representative per D4 orbit.

    Policies are projected onto the canonical state's stabilizer before being
    mapped back. This retains exact equivariance even for highly symmetric
    states, while requiring only one neural evaluation per distinct orbit.
    """

    def __init__(self, base: PositionEvaluator, *, maximum_batch_size: int = 256) -> None:
        if maximum_batch_size < 1:
            raise ValueError("maximum canonical-evaluator batch size must be positive")
        self.base = base
        self.maximum_batch_size = maximum_batch_size

    def evaluate(self, states: Sequence[_escape_core.State]) -> list[Evaluation]:
        if not states:
            return []
        canonicalized = [_canonical_position(state) for state in states]
        unique = {item.key: item.state for item in canonicalized}
        ordered = sorted(unique.items())
        canonical_evaluations: list[Evaluation] = []
        canonical_states = [canonical for _key, canonical in ordered]
        for first in range(0, len(canonical_states), self.maximum_batch_size):
            batch = canonical_states[first : first + self.maximum_batch_size]
            evaluated = self.base.evaluate(batch)
            if len(evaluated) != len(batch):
                raise AssertionError("base evaluator returned the wrong batch length")
            canonical_evaluations.extend(evaluated)

        evaluation_by_key: dict[bytes, Evaluation] = {}
        for (key, canonical), evaluation in zip(
            ordered, canonical_evaluations, strict=True
        ):
            normalized = _normalized_legal_policy(canonical, evaluation.priors)
            stabilized = _stabilize_canonical_policy(canonical, normalized)
            evaluation_by_key[key] = Evaluation(stabilized, evaluation.value)

        return [
            Evaluation(
                _map_policy_to_source(
                    state,
                    evaluation_by_key[item.key].priors,
                    item.source_to_canonical,
                ),
                evaluation_by_key[item.key].value,
            )
            for state, item in zip(states, canonicalized, strict=True)
        ]


class D4SymmetryEnsembleEvaluator:
    """Average a base evaluator over the role-aware D4 orbit of each state.

    Equivalent positions in one call are canonicalized and deduplicated. This
    both avoids repeated network work and makes their returned values/policies
    exact coordinate permutations of the same accumulated result.
    """

    def __init__(self, base: PositionEvaluator, *, maximum_batch_size: int = 256) -> None:
        if maximum_batch_size < 1:
            raise ValueError("maximum symmetry-ensemble batch size must be positive")
        self.base = base
        self.maximum_batch_size = maximum_batch_size

    def evaluate(self, states: Sequence[_escape_core.State]) -> list[Evaluation]:
        if not states:
            return []
        canonicalized = [_canonical_position(state) for state in states]
        unique = {item.key: item.state for item in canonicalized}
        ordered = sorted(unique.items())
        oriented_states = [
            canonical.transformed(symmetry)
            for _key, canonical in ordered
            for symmetry in D4_SYMMETRIES
        ]
        oriented_evaluations: list[Evaluation] = []
        for first in range(0, len(oriented_states), self.maximum_batch_size):
            batch = oriented_states[first : first + self.maximum_batch_size]
            evaluated = self.base.evaluate(batch)
            if len(evaluated) != len(batch):
                raise AssertionError("base evaluator returned the wrong batch length")
            oriented_evaluations.extend(evaluated)

        ensemble_by_key: dict[bytes, Evaluation] = {}
        orbit_width = len(D4_SYMMETRIES)
        for canonical_index, (key, canonical) in enumerate(ordered):
            policy_sum = np.zeros((canonical.size + 1) ** 2, dtype=np.float64)
            value_sum = 0.0
            for offset, symmetry in enumerate(D4_SYMMETRIES):
                evaluation = oriented_evaluations[canonical_index * orbit_width + offset]
                expected_shape = ((canonical.size + 1) ** 2,)
                if evaluation.priors.shape != expected_shape:
                    raise ValueError("base evaluator policy has the wrong action-space shape")
                policy_sum += _map_policy_to_source(
                    canonical,
                    evaluation.priors,
                    symmetry,
                )
                value_sum += evaluation.value

            legal = np.asarray(canonical.legal_actions(), dtype=np.int64)
            policy = np.zeros((canonical.size + 1) ** 2, dtype=np.float32)
            legal_weights = np.maximum(policy_sum[legal], 0.0)
            total = float(legal_weights.sum())
            if not math.isfinite(total) or total <= 0.0:
                legal_weights.fill(1.0 / len(legal))
            else:
                legal_weights /= total
            policy[legal] = legal_weights.astype(np.float32)
            ensemble_by_key[key] = Evaluation(policy, value_sum / orbit_width)

        return [
            Evaluation(
                _map_policy_to_source(
                    state,
                    ensemble_by_key[item.key].priors,
                    item.source_to_canonical,
                ),
                ensemble_by_key[item.key].value,
            )
            for state, item in zip(states, canonicalized, strict=True)
        ]
