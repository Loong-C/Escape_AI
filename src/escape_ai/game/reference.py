"""Slow, direct and auditable implementation of the Escape rules."""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from math import inf, isfinite

from .types import (
    DIRECTION_ORDER,
    Cell,
    Direction,
    DirectionalDistances,
    GameState,
    LegalMove,
    MoveKind,
    MoveRecord,
    Outcome,
    OutcomeStatus,
    Player,
    ShortestEscapeInfo,
    WalkResult,
    WallSegment,
    WinReason,
)

DIRECTION_DELTAS: dict[Direction, tuple[int, int]] = {
    Direction.UP: (-1, 0),
    Direction.RIGHT: (0, 1),
    Direction.DOWN: (1, 0),
    Direction.LEFT: (0, -1),
}


def _assert_board_size(size: int) -> None:
    if size < 3 or size > 17 or size % 2 == 0:
        raise ValueError("board size must be an odd integer from 3 through 17")


def _assert_state_shape(state: GameState) -> None:
    _assert_board_size(state.size)
    if len(state.posts) != (state.size + 1) ** 2:
        raise ValueError("post array length does not match the board size")
    if not _cell_inside(state.size, state.ball.row, state.ball.col):
        raise ValueError("ball is outside the board")
    if state.ply < 0 or state.ply > 2 * (state.size + 1) ** 2:
        raise ValueError("ply is outside the theoretical game-length bound")


def create_game(size: int = 17) -> GameState:
    """Create an empty odd-sized board with White to move."""

    _assert_board_size(size)
    center = size // 2
    return GameState(
        size=size,
        posts=(None,) * ((size + 1) ** 2),
        ball=Cell(center, center),
        turn=Player.WHITE,
        ply=0,
        outcome=Outcome.playing(),
    )


def other_player(player: Player) -> Player:
    return Player.BLACK if player is Player.WHITE else Player.WHITE


def vertex_index(size: int, row: int, col: int) -> int:
    return row * (size + 1) + col


def _vertex_inside(size: int, row: int, col: int) -> bool:
    return 0 <= row <= size and 0 <= col <= size


def _cell_inside(size: int, row: int, col: int) -> bool:
    return 0 <= row < size and 0 <= col < size


def get_post(state: GameState, row: int, col: int) -> Player | None:
    if not _vertex_inside(state.size, row, col):
        return None
    return state.posts[vertex_index(state.size, row, col)]


def set_post(state: GameState, row: int, col: int, post: Player | None) -> GameState:
    """Return a setup state with one vertex changed, without applying a turn."""

    if not _vertex_inside(state.size, row, col):
        raise ValueError(f"vertex outside board: ({row}, {col})")
    posts = list(state.posts)
    posts[vertex_index(state.size, row, col)] = post
    return replace(state, posts=tuple(posts))


def _has_same_color_neighbor(
    state: GameState,
    row: int,
    col: int,
    color: Player,
) -> bool:
    return any(
        get_post(state, row + delta_row, col + delta_col) is color
        for delta_row, delta_col in DIRECTION_DELTAS.values()
    )


def is_anchored(state: GameState, row: int, col: int) -> bool:
    color = get_post(state, row, col)
    return color is not None and _has_same_color_neighbor(state, row, col, color)


def legal_move(state: GameState, action: int) -> LegalMove | None:
    if state.outcome.status is not OutcomeStatus.PLAYING:
        return None
    action_count = (state.size + 1) ** 2
    if action < 0 or action >= action_count:
        return None
    row, col = divmod(action, state.size + 1)
    occupant = get_post(state, row, col)
    if occupant is None:
        return LegalMove(action, row, col, MoveKind.PLACE)
    if (
        occupant is other_player(state.turn)
        and not is_anchored(state, row, col)
        and _has_same_color_neighbor(state, row, col, state.turn)
    ):
        return LegalMove(action, row, col, MoveKind.REPLACE)
    return None


def list_legal_moves(state: GameState) -> tuple[LegalMove, ...]:
    if state.outcome.status is not OutcomeStatus.PLAYING:
        return ()
    moves = (legal_move(state, action) for action in range((state.size + 1) ** 2))
    return tuple(move for move in moves if move is not None)


def list_walls(state: GameState) -> tuple[WallSegment, ...]:
    walls: list[WallSegment] = []
    for row in range(state.size + 1):
        for col in range(state.size + 1):
            color = get_post(state, row, col)
            if color is None:
                continue
            if col < state.size and get_post(state, row, col + 1) is color:
                walls.append(WallSegment("horizontal", row, col, color))
            if row < state.size and get_post(state, row + 1, col) is color:
                walls.append(WallSegment("vertical", row, col, color))
    return tuple(walls)


def _has_horizontal_wall(state: GameState, row: int, col: int) -> bool:
    left = get_post(state, row, col)
    return left is not None and get_post(state, row, col + 1) is left


def _has_vertical_wall(state: GameState, row: int, col: int) -> bool:
    top = get_post(state, row, col)
    return top is not None and get_post(state, row + 1, col) is top


def is_passage_blocked(state: GameState, cell: Cell, direction: Direction) -> bool:
    if direction is Direction.UP:
        return _has_horizontal_wall(state, cell.row, cell.col)
    if direction is Direction.RIGHT:
        return _has_vertical_wall(state, cell.row, cell.col + 1)
    if direction is Direction.DOWN:
        return _has_horizontal_wall(state, cell.row + 1, cell.col)
    return _has_vertical_wall(state, cell.row, cell.col)


def walk(state: GameState, cell: Cell, direction: Direction) -> WalkResult | None:
    if not _cell_inside(state.size, cell.row, cell.col):
        raise ValueError(f"cell outside board: ({cell.row}, {cell.col})")
    if is_passage_blocked(state, cell, direction):
        return None
    delta_row, delta_col = DIRECTION_DELTAS[direction]
    next_cell = Cell(cell.row + delta_row, cell.col + delta_col)
    if _cell_inside(state.size, next_cell.row, next_cell.col):
        return WalkResult(cell=next_cell)
    return WalkResult(exit_direction=direction)


def _nearest_exit_distances(state: GameState) -> tuple[float, ...]:
    distances = [inf] * (state.size * state.size)
    queue: deque[Cell] = deque()

    for row in range(state.size):
        for col in range(state.size):
            cell = Cell(row, col)
            if any(
                (step := walk(state, cell, direction)) is not None and step.is_exit
                for direction in DIRECTION_ORDER
            ):
                distances[row * state.size + col] = 1
                queue.append(cell)

    while queue:
        current = queue.popleft()
        current_distance = distances[current.row * state.size + current.col]
        for direction in DIRECTION_ORDER:
            step = walk(state, current, direction)
            if step is None or step.cell is None:
                continue
            index = step.cell.row * state.size + step.cell.col
            if distances[index] <= current_distance + 1:
                continue
            distances[index] = current_distance + 1
            queue.append(step.cell)
    return tuple(distances)


def first_step_costs(state: GameState, from_cell: Cell | None = None) -> DirectionalDistances:
    """Return c_up,c_right,c_down,c_left, including the first step itself."""

    origin = from_cell if from_cell is not None else state.ball
    distances = _nearest_exit_distances(state)
    costs: dict[Direction, float] = {}
    for direction in DIRECTION_ORDER:
        step = walk(state, origin, direction)
        if step is None:
            costs[direction] = inf
        elif step.is_exit:
            costs[direction] = 1
        else:
            assert step.cell is not None
            remaining = distances[step.cell.row * state.size + step.cell.col]
            costs[direction] = 1 + remaining
    return DirectionalDistances(
        up=costs[Direction.UP],
        right=costs[Direction.RIGHT],
        down=costs[Direction.DOWN],
        left=costs[Direction.LEFT],
    )


def shortest_escape(state: GameState) -> ShortestEscapeInfo:
    costs = first_step_costs(state)
    distance = min(costs.as_tuple())
    if not isfinite(distance):
        return ShortestEscapeInfo(inf, ())
    first_steps = tuple(direction for direction in DIRECTION_ORDER if costs[direction] == distance)
    return ShortestEscapeInfo(distance, first_steps)


def directional_exit_distances(
    state: GameState,
    from_cell: Cell | None = None,
) -> DirectionalDistances:
    """Return the shortest path length to each of the four boundary sides."""

    origin = from_cell if from_cell is not None else state.ball
    distances = [inf] * (state.size * state.size)
    queue: deque[Cell] = deque([origin])
    distances[origin.row * state.size + origin.col] = 0
    exits = {direction: inf for direction in DIRECTION_ORDER}

    while queue:
        current = queue.popleft()
        current_distance = distances[current.row * state.size + current.col]
        for direction in DIRECTION_ORDER:
            step = walk(state, current, direction)
            if step is None:
                continue
            if step.is_exit:
                exits[direction] = min(exits[direction], current_distance + 1)
                continue
            assert step.cell is not None
            index = step.cell.row * state.size + step.cell.col
            if distances[index] != inf:
                continue
            distances[index] = current_distance + 1
            queue.append(step.cell)

    return DirectionalDistances(
        up=exits[Direction.UP],
        right=exits[Direction.RIGHT],
        down=exits[Direction.DOWN],
        left=exits[Direction.LEFT],
    )


def _winner_for_exit(direction: Direction) -> Player:
    return Player.WHITE if direction in (Direction.LEFT, Direction.RIGHT) else Player.BLACK


def apply_action(state: GameState, action: int) -> GameState:
    _assert_state_shape(state)
    move = legal_move(state, action)
    if move is None:
        raise ValueError(f"illegal action: {action}")

    ball_before = state.ball
    posts = list(state.posts)
    posts[action] = state.turn
    placed = replace(state, posts=tuple(posts))
    costs = first_step_costs(placed)
    shortest = shortest_escape(placed)
    ball_after: Cell | None = ball_before
    escaped_through: Direction | None = None
    outcome = Outcome.playing()
    ball = ball_before

    if not isfinite(shortest.distance):
        outcome = Outcome.won(state.turn, WinReason.TRAPPED)
    elif len(shortest.first_steps) == 1:
        direction = shortest.first_steps[0]
        step = walk(placed, ball_before, direction)
        if step is None:
            raise AssertionError("a shortest first step cannot be blocked")
        if step.is_exit:
            escaped_through = direction
            ball_after = None
            outcome = Outcome.won(
                _winner_for_exit(direction),
                WinReason.ESCAPED,
                direction,
            )
        else:
            assert step.cell is not None
            ball = step.cell
            ball_after = ball

    record = MoveRecord(
        player=state.turn,
        move=move,
        ball_before=ball_before,
        ball_after=ball_after,
        escaped_through=escaped_through,
        first_step_costs=costs,
        shortest=shortest,
    )
    next_state = replace(
        placed,
        ball=ball,
        ply=state.ply + 1,
        outcome=outcome,
        last_move=record,
    )
    if outcome.status is OutcomeStatus.WON:
        return next_state
    next_state = replace(next_state, turn=other_player(state.turn))
    return adjudicate_turn_start(next_state)


def apply_move(state: GameState, row: int, col: int) -> GameState:
    if not _vertex_inside(state.size, row, col):
        raise ValueError(f"vertex outside board: ({row}, {col})")
    return apply_action(state, vertex_index(state.size, row, col))


def adjudicate_turn_start(state: GameState) -> GameState:
    if state.outcome.status is OutcomeStatus.PLAYING and not list_legal_moves(state):
        return replace(state, outcome=Outcome.draw())
    return state


def count_posts(state: GameState, player: Player) -> int:
    return sum(post is player for post in state.posts)


def count_anchored_posts(state: GameState, player: Player) -> int:
    return sum(
        get_post(state, row, col) is player and is_anchored(state, row, col)
        for row in range(state.size + 1)
        for col in range(state.size + 1)
    )
