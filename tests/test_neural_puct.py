from __future__ import annotations

import random

import numpy as np
import pytest
import torch

from escape_ai import _escape_core
from escape_ai.search import PUCTSearch, TorchEvaluator, UniformEvaluator
from escape_ai.training import NetworkConfig, PolicyValueNet, encode_state, legal_action_mask


def trapping_position() -> _escape_core.State:
    state = _escape_core.State(3)
    state.set_post(1, 1, "white")
    state.set_post(1, 2, "white")
    state.set_post(2, 1, "white")
    return state


def test_state_encoding_contains_posts_ball_walls_and_turn() -> None:
    state = _escape_core.State(3)
    state.set_post(0, 0, "white")
    state.set_post(0, 1, "white")
    state.set_post(2, 2, "black")
    encoded = encode_state(state)
    assert encoded.shape == (6, 4, 4)
    assert encoded.dtype == np.float32
    assert encoded[0, 0, 0] == 1
    assert encoded[1, 2, 2] == 1
    assert encoded[2].sum() == 4
    assert encoded[3, 0, 0] == 1
    assert encoded[3, 0, 1] == 1
    assert encoded[4].sum() == 0
    assert encoded[5].min() == 1


def test_encoding_is_equivariant_under_d4_with_color_axis_swaps() -> None:
    state = _escape_core.State(5)
    for action in (0, 1, 7, 8, 20):
        state = state.apply(action)
        if state.outcome["status"] != "playing":
            break
    original = encode_state(state)
    geometric_transforms = {
        _escape_core.Symmetry.IDENTITY: lambda array: array,
        _escape_core.Symmetry.ROTATE_90: lambda array: np.rot90(array, -1, axes=(1, 2)),
        _escape_core.Symmetry.ROTATE_180: lambda array: np.rot90(array, 2, axes=(1, 2)),
        _escape_core.Symmetry.ROTATE_270: lambda array: np.rot90(array, 1, axes=(1, 2)),
        _escape_core.Symmetry.FLIP_HORIZONTAL: lambda array: np.flip(array, axis=1),
        _escape_core.Symmetry.FLIP_VERTICAL: lambda array: np.flip(array, axis=2),
        _escape_core.Symmetry.DIAGONAL_MAIN: lambda array: np.swapaxes(array, 1, 2),
        _escape_core.Symmetry.DIAGONAL_ANTI: lambda array: np.rot90(
            np.swapaxes(array, 1, 2), 2, axes=(1, 2)
        ),
    }
    axis_swaps = {
        _escape_core.Symmetry.ROTATE_90,
        _escape_core.Symmetry.ROTATE_270,
        _escape_core.Symmetry.DIAGONAL_MAIN,
        _escape_core.Symmetry.DIAGONAL_ANTI,
    }
    for symmetry, transform in geometric_transforms.items():
        expected = transform(original).copy()
        if symmetry in axis_swaps:
            expected[[0, 1]] = expected[[1, 0]]
            expected[[3, 4]] = expected[[4, 3]]
            expected[5] = 1.0 - expected[5]
        actual = encode_state(state.transformed(symmetry))
        np.testing.assert_array_equal(actual, expected)


def test_legal_action_mask_matches_engine() -> None:
    state = trapping_position()
    mask = legal_action_mask(state)
    assert mask.dtype == np.bool_
    assert np.flatnonzero(mask).tolist() == state.legal_actions()


def test_policy_value_network_supports_multiple_board_sizes() -> None:
    torch.manual_seed(7)
    model = PolicyValueNet(NetworkConfig(channels=16, residual_blocks=2, value_hidden=8))
    for size in (3, 17):
        inputs = torch.from_numpy(encode_state(_escape_core.State(size))).unsqueeze(0)
        logits, value = model(inputs)
        assert logits.shape == (1, (size + 1) ** 2)
        assert value.shape == (1,)
        assert -1.0 <= value.item() <= 1.0


def test_torch_evaluator_masks_illegal_actions() -> None:
    model = PolicyValueNet(NetworkConfig(channels=8, residual_blocks=1, value_hidden=4))
    state = trapping_position()
    result = TorchEvaluator(model, "cpu").evaluate([state])[0]
    assert set(result.priors) == set(state.legal_actions())
    assert sum(result.priors.values()) == pytest.approx(1.0)


def test_puct_finds_and_values_an_immediate_win() -> None:
    state = trapping_position()
    search = PUCTSearch(UniformEvaluator(), simulations=128, c_puct=1.5)
    result = search.run(state, random.Random(7))
    child = state.apply(result.action)
    assert child.outcome["winner"] == "white"
    winning = [item for item in result.statistics if state.apply(item.action).outcome["winner"]]
    assert winning
    assert max(item.mean_value for item in winning) == 1.0
    assert result.policy.sum() == pytest.approx(1.0)
