"""Value types shared by Escape rules implementations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import inf


class Player(StrEnum):
    WHITE = "white"
    BLACK = "black"


class Direction(StrEnum):
    UP = "up"
    RIGHT = "right"
    DOWN = "down"
    LEFT = "left"


DIRECTION_ORDER = (Direction.UP, Direction.RIGHT, Direction.DOWN, Direction.LEFT)


class MoveKind(StrEnum):
    PLACE = "place"
    REPLACE = "replace"


class OutcomeStatus(StrEnum):
    PLAYING = "playing"
    WON = "won"
    DRAW = "draw"


class WinReason(StrEnum):
    ESCAPED = "escaped"
    TRAPPED = "trapped"
    NO_LEGAL_MOVES = "no-legal-moves"


class Symmetry(StrEnum):
    IDENTITY = "identity"
    ROTATE_90 = "rotate-90"
    ROTATE_180 = "rotate-180"
    ROTATE_270 = "rotate-270"
    FLIP_HORIZONTAL = "flip-horizontal"
    FLIP_VERTICAL = "flip-vertical"
    DIAGONAL_MAIN = "diagonal-main"
    DIAGONAL_ANTI = "diagonal-anti"


@dataclass(frozen=True, slots=True, order=True)
class Cell:
    row: int
    col: int


@dataclass(frozen=True, slots=True)
class LegalMove:
    action: int
    row: int
    col: int
    kind: MoveKind


@dataclass(frozen=True, slots=True)
class DirectionalDistances:
    up: float = inf
    right: float = inf
    down: float = inf
    left: float = inf

    def __getitem__(self, direction: Direction) -> float:
        return {
            Direction.UP: self.up,
            Direction.RIGHT: self.right,
            Direction.DOWN: self.down,
            Direction.LEFT: self.left,
        }[direction]

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.up, self.right, self.down, self.left)


@dataclass(frozen=True, slots=True)
class ShortestEscapeInfo:
    distance: float
    first_steps: tuple[Direction, ...]


@dataclass(frozen=True, slots=True)
class Outcome:
    status: OutcomeStatus
    winner: Player | None = None
    reason: WinReason | None = None
    exit_direction: Direction | None = None

    @classmethod
    def playing(cls) -> Outcome:
        return cls(OutcomeStatus.PLAYING)

    @classmethod
    def draw(cls) -> Outcome:
        return cls(OutcomeStatus.DRAW, reason=WinReason.NO_LEGAL_MOVES)

    @classmethod
    def won(
        cls,
        winner: Player,
        reason: WinReason,
        exit_direction: Direction | None = None,
    ) -> Outcome:
        return cls(OutcomeStatus.WON, winner, reason, exit_direction)


@dataclass(frozen=True, slots=True)
class MoveRecord:
    player: Player
    move: LegalMove
    ball_before: Cell
    ball_after: Cell | None
    escaped_through: Direction | None
    first_step_costs: DirectionalDistances
    shortest: ShortestEscapeInfo


@dataclass(frozen=True, slots=True)
class GameState:
    size: int
    posts: tuple[Player | None, ...]
    ball: Cell
    turn: Player
    ply: int
    outcome: Outcome
    last_move: MoveRecord | None = None


@dataclass(frozen=True, slots=True)
class WallSegment:
    orientation: str
    row: int
    col: int
    color: Player


@dataclass(frozen=True, slots=True)
class WalkResult:
    cell: Cell | None = None
    exit_direction: Direction | None = None

    @property
    def is_exit(self) -> bool:
        return self.exit_direction is not None
