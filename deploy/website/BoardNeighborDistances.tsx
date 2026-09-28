import type { CSSProperties } from "react";
import {
  DIRECTIONS,
  type Cell,
  type Direction,
  type DirectionalDistances,
} from "../game";

interface BoardNeighborDistancesProps {
  ball: Cell;
  boardSize: number;
  distances: DirectionalDistances;
  highlightShortest?: boolean;
}

const DIRECTION_LABELS: Record<Direction, string> = {
  up: "首步向上",
  right: "首步向右",
  down: "首步向下",
  left: "首步向左",
};

const DIRECTION_DELTAS: Record<Direction, Cell> = {
  up: { row: -1, col: 0 },
  right: { row: 0, col: 1 },
  down: { row: 1, col: 0 },
  left: { row: 0, col: -1 },
};

const BOARD_MARGIN_RATIO = 0.104;
const BOARD_LENGTH_RATIO = 0.792;

function formatDistance(value: number): string {
  return Number.isFinite(value) ? String(value) : "∞";
}

function positionForDirection(
  ball: Cell,
  boardSize: number,
  direction: Direction,
): CSSProperties {
  const delta = DIRECTION_DELTAS[direction];
  const step = BOARD_LENGTH_RATIO / boardSize;
  const x = BOARD_MARGIN_RATIO + (ball.col + 0.5 + delta.col) * step;
  const y = BOARD_MARGIN_RATIO + (ball.row + 0.5 + delta.row) * step;
  return { left: `${x * 100}%`, top: `${y * 100}%` };
}

export function BoardNeighborDistances({
  ball,
  boardSize,
  distances: remainingDistances,
  highlightShortest = false,
}: BoardNeighborDistancesProps) {
  // Engine values exclude the first step; every visible hint includes it.
  const distances: DirectionalDistances = {
    up: remainingDistances.up + 1,
    right: remainingDistances.right + 1,
    down: remainingDistances.down + 1,
    left: remainingDistances.left + 1,
  };
  const shortest = Math.min(...DIRECTIONS.map((direction) => distances[direction]));
  const shortestDirections = DIRECTIONS.filter(
    (direction) => distances[direction] === shortest,
  );
  const uniqueShortest = shortestDirections.length === 1 ? shortestDirections[0] : null;
  const announcement = DIRECTIONS.map(
    (direction) => `${DIRECTION_LABELS[direction]} ${formatDistance(distances[direction])} 步`,
  ).join("；");

  return (
    <div className="neighbor-distances" aria-live="polite" aria-atomic="true">
      <span className="visually-hidden">{announcement}</span>
      {DIRECTIONS.map((direction) => {
        const isShortest = highlightShortest && direction === uniqueShortest;
        return (
          <div
            className={`neighbor-distance${isShortest ? " is-shortest" : ""}`}
            data-direction={direction}
            key={direction}
            style={positionForDirection(ball, boardSize, direction)}
            aria-hidden="true"
          >
            {formatDistance(distances[direction])}
          </div>
        );
      })}
    </div>
  );
}
