from __future__ import annotations

from pathlib import Path

import pytest

from escape_ai import _escape_core
from escape_ai.research.symmetry_audit import (
    _SYMMETRIES,
    assert_legal_action_equivariance,
    load_symmetry_audit_config,
    symmetry_swaps_roles,
    transform_equivalent_state,
)


def _fixture_state() -> _escape_core.State:
    state = _escape_core.State(3)
    for action in (0, 1, 4, 2, 8):
        state = state.apply(action)
    return state


@pytest.mark.parametrize("symmetry", _SYMMETRIES)
def test_role_aware_symmetry_preserves_legal_transitions(
    symmetry: _escape_core.Symmetry,
) -> None:
    state = _fixture_state()
    transformed = transform_equivalent_state(state, symmetry)
    assert_legal_action_equivariance(state, transformed, symmetry)

    for action in state.legal_actions():
        expected = state.apply(action).transformed(symmetry)
        observed = transformed.apply(
            _escape_core.transform_action(action, state.size, symmetry)
        )
        assert observed.serialize() == expected.serialize()


@pytest.mark.parametrize("symmetry", _SYMMETRIES)
def test_axis_swapping_symmetries_exchange_roles(
    symmetry: _escape_core.Symmetry,
) -> None:
    state = _fixture_state()
    transformed = transform_equivalent_state(state, symmetry)
    expected_turn = "white" if symmetry_swaps_roles(symmetry) else "black"

    assert state.turn == "black"
    assert transformed.turn == expected_turn
    expected_white_count = (
        state.posts.count("black")
        if symmetry_swaps_roles(symmetry)
        else state.posts.count("white")
    )
    expected_black_count = (
        state.posts.count("white")
        if symmetry_swaps_roles(symmetry)
        else state.posts.count("black")
    )
    assert transformed.posts.count("white") == expected_white_count
    assert transformed.posts.count("black") == expected_black_count


def test_committed_symmetry_audit_locks_sampling_and_search_budget() -> None:
    config = load_symmetry_audit_config(
        Path("configs/symmetry/champion-symmetry-audit-17x17-v1.yaml")
    )

    assert config.run_id == "champion-symmetry-audit-17x17-v1"
    assert config.samples_per_stratum == 128
    assert config.search.samples_per_stratum == 4
    assert config.search.simulations == 512
    assert config.decision_thresholds.maximum_neural_p95_policy_l1 == 0.25
    assert config.checkpoint.sha256 == (
        "0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3"
    )
