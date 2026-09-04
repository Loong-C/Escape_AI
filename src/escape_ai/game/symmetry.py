"""D4 transforms, including Escape's goal-axis color swaps."""

from __future__ import annotations

from dataclasses import replace

from .types import Cell, Direction, GameState, Outcome, OutcomeStatus, Player, Symmetry

AXIS_SWAPPING_SYMMETRIES = frozenset(
    {
        Symmetry.ROTATE_90,
        Symmetry.ROTATE_270,
        Symmetry.DIAGONAL_MAIN,
        Symmetry.DIAGONAL_ANTI,
    }
)


def _transform_coordinate(row: int, col: int, extent: int, symmetry: Symmetry) -> Cell:
    last = extent - 1
    if symmetry is Symmetry.IDENTITY:
        return Cell(row, col)
    if symmetry is Symmetry.ROTATE_90:
        return Cell(col, last - row)
    if symmetry is Symmetry.ROTATE_180:
        return Cell(last - row, last - col)
    if symmetry is Symmetry.ROTATE_270:
        return Cell(last - col, row)
    if symmetry is Symmetry.FLIP_HORIZONTAL:
        return Cell(last - row, col)
    if symmetry is Symmetry.FLIP_VERTICAL:
        return Cell(row, last - col)
    if symmetry is Symmetry.DIAGONAL_MAIN:
        return Cell(col, row)
    return Cell(last - col, last - row)


def transform_cell(cell: Cell, size: int, symmetry: Symmetry) -> Cell:
    return _transform_coordinate(cell.row, cell.col, size, symmetry)


def transform_vertex(row: int, col: int, size: int, symmetry: Symmetry) -> Cell:
    return _transform_coordinate(row, col, size + 1, symmetry)


def transform_action(action: int, size: int, symmetry: Symmetry) -> int:
    row, col = divmod(action, size + 1)
    transformed = transform_vertex(row, col, size, symmetry)
    return transformed.row * (size + 1) + transformed.col


def transform_player(player: Player, symmetry: Symmetry) -> Player:
    if symmetry not in AXIS_SWAPPING_SYMMETRIES:
        return player
    return Player.BLACK if player is Player.WHITE else Player.WHITE


_DIRECTION_TRANSFORMS: dict[Symmetry, dict[Direction, Direction]] = {
    Symmetry.IDENTITY: {
        Direction.UP: Direction.UP,
        Direction.RIGHT: Direction.RIGHT,
        Direction.DOWN: Direction.DOWN,
        Direction.LEFT: Direction.LEFT,
    },
    Symmetry.ROTATE_90: {
        Direction.UP: Direction.RIGHT,
        Direction.RIGHT: Direction.DOWN,
        Direction.DOWN: Direction.LEFT,
        Direction.LEFT: Direction.UP,
    },
    Symmetry.ROTATE_180: {
        Direction.UP: Direction.DOWN,
        Direction.RIGHT: Direction.LEFT,
        Direction.DOWN: Direction.UP,
        Direction.LEFT: Direction.RIGHT,
    },
    Symmetry.ROTATE_270: {
        Direction.UP: Direction.LEFT,
        Direction.RIGHT: Direction.UP,
        Direction.DOWN: Direction.RIGHT,
        Direction.LEFT: Direction.DOWN,
    },
    Symmetry.FLIP_HORIZONTAL: {
        Direction.UP: Direction.DOWN,
        Direction.RIGHT: Direction.RIGHT,
        Direction.DOWN: Direction.UP,
        Direction.LEFT: Direction.LEFT,
    },
    Symmetry.FLIP_VERTICAL: {
        Direction.UP: Direction.UP,
        Direction.RIGHT: Direction.LEFT,
        Direction.DOWN: Direction.DOWN,
        Direction.LEFT: Direction.RIGHT,
    },
    Symmetry.DIAGONAL_MAIN: {
        Direction.UP: Direction.LEFT,
        Direction.RIGHT: Direction.DOWN,
        Direction.DOWN: Direction.RIGHT,
        Direction.LEFT: Direction.UP,
    },
    Symmetry.DIAGONAL_ANTI: {
        Direction.UP: Direction.RIGHT,
        Direction.RIGHT: Direction.UP,
        Direction.DOWN: Direction.LEFT,
        Direction.LEFT: Direction.DOWN,
    },
}


def transform_direction(direction: Direction, symmetry: Symmetry) -> Direction:
    return _DIRECTION_TRANSFORMS[symmetry][direction]


def _transform_outcome(outcome: Outcome, symmetry: Symmetry) -> Outcome:
    if outcome.status is OutcomeStatus.PLAYING:
        return Outcome.playing()
    if outcome.status is OutcomeStatus.DRAW:
        return Outcome.draw()
    assert outcome.winner is not None and outcome.reason is not None
    exit_direction = (
        transform_direction(outcome.exit_direction, symmetry)
        if outcome.exit_direction is not None
        else None
    )
    return Outcome.won(
        transform_player(outcome.winner, symmetry),
        outcome.reason,
        exit_direction,
    )


def transform_state(state: GameState, symmetry: Symmetry) -> GameState:
    """Transform canonical rules state; last-move annotations are intentionally dropped."""

    posts: list[Player | None] = [None] * len(state.posts)
    for row in range(state.size + 1):
        for col in range(state.size + 1):
            source_index = row * (state.size + 1) + col
            post = state.posts[source_index]
            target = transform_vertex(row, col, state.size, symmetry)
            target_index = target.row * (state.size + 1) + target.col
            posts[target_index] = transform_player(post, symmetry) if post is not None else None
    return replace(
        state,
        posts=tuple(posts),
        ball=transform_cell(state.ball, state.size, symmetry),
        turn=transform_player(state.turn, symmetry),
        outcome=_transform_outcome(state.outcome, symmetry),
        last_move=None,
    )
