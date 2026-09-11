"""Shared role-aware D4 coordinate utilities for search."""

from __future__ import annotations

from escape_ai import _escape_core

D4_SYMMETRIES = (
    _escape_core.Symmetry.IDENTITY,
    _escape_core.Symmetry.ROTATE_90,
    _escape_core.Symmetry.ROTATE_180,
    _escape_core.Symmetry.ROTATE_270,
    _escape_core.Symmetry.FLIP_HORIZONTAL,
    _escape_core.Symmetry.FLIP_VERTICAL,
    _escape_core.Symmetry.DIAGONAL_MAIN,
    _escape_core.Symmetry.DIAGONAL_ANTI,
)


def canonical_symmetry(state: _escape_core.State) -> _escape_core.Symmetry:
    """Return a deterministic transform from this state to its D4 canonical form."""

    return min(
        (
            state.transformed(symmetry).serialize(),
            index,
            symmetry,
        )
        for index, symmetry in enumerate(D4_SYMMETRIES)
    )[2]


def canonical_action_order(
    state: _escape_core.State,
    actions: list[int],
    symmetry: _escape_core.Symmetry | None = None,
) -> list[int]:
    """Sort source actions by their index in the state's canonical orientation."""

    selected = symmetry if symmetry is not None else canonical_symmetry(state)
    return sorted(
        actions,
        key=lambda action: _escape_core.transform_action(action, state.size, selected),
    )
