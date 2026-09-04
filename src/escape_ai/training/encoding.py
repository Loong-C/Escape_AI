"""Canonical neural-network feature and action encodings."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from escape_ai import _escape_core

INPUT_CHANNELS = 6


def encode_state(state: _escape_core.State) -> npt.NDArray[np.float32]:
    """Encode a state as white, black, ball, H-wall, V-wall, turn planes."""

    width = state.size + 1
    planes = np.zeros((INPUT_CHANNELS, width, width), dtype=np.float32)
    posts = np.asarray(state.posts, dtype=object).reshape((width, width))
    planes[0] = posts == "white"
    planes[1] = posts == "black"

    ball_row, ball_col = state.ball
    # Mark the four post-grid corners of the occupied cell. Unlike a top-left
    # marker, this representation is equivariant under every D4 transform of
    # the (size + 1) x (size + 1) post lattice.
    planes[2, ball_row : ball_row + 2, ball_col : ball_col + 2] = 1.0
    for orientation, row, col, _color in state.walls():
        if orientation == "horizontal":
            planes[3, row, col : col + 2] = 1.0
        else:
            planes[4, row : row + 2, col] = 1.0
    if state.turn == "white":
        planes[5].fill(1.0)
    return planes


def legal_action_mask(state: _escape_core.State) -> npt.NDArray[np.bool_]:
    """Return a flat mask in the shared post-index action encoding."""

    mask = np.zeros((state.size + 1) ** 2, dtype=np.bool_)
    mask[state.legal_actions()] = True
    return mask
