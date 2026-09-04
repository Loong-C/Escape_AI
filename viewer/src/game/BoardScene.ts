import Phaser from "phaser";

import type { BoardState, Player } from "../types";

export interface BoardView {
  state: BoardState;
  highlightedAction: number | null;
}

const CANVAS_SIZE = 1000;
const BOARD_MARGIN = 94;
const BOARD_LENGTH = CANVAS_SIZE - BOARD_MARGIN * 2;

const COLORS = {
  background: 0x15181c,
  board: 0x1d2126,
  boardInset: 0x20252b,
  grid: 0x3b424b,
  boundary: 0x8d96a1,
  emptyPoint: 0x77808b,
  black: 0x08090b,
  blackOutline: 0x727b86,
  white: 0xf2f4f6,
  whiteOutline: 0xb4bac2,
  accent: 0x6d96ef,
  target: 0x5f8dea,
} as const;

export class BoardScene extends Phaser.Scene {
  private view: BoardView | null = null;

  constructor() {
    super({ key: "research-board" });
  }

  create(): void {
    this.renderBoard();
  }

  setView(view: BoardView): void {
    this.view = view;
    if (this.sys.isActive()) {
      this.renderBoard();
    }
  }

  private point(size: number, row: number, col: number): Phaser.Math.Vector2 {
    const step = BOARD_LENGTH / size;
    return new Phaser.Math.Vector2(
      BOARD_MARGIN + col * step,
      BOARD_MARGIN + row * step,
    );
  }

  private renderBoard(): void {
    this.children.removeAll(true);
    if (!this.view) return;

    const { state, highlightedAction } = this.view;
    const graphics = this.add.graphics();
    graphics.fillStyle(COLORS.background, 1);
    graphics.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    graphics.fillStyle(COLORS.boardInset, 1);
    graphics.fillRoundedRect(
      BOARD_MARGIN - 28,
      BOARD_MARGIN - 28,
      BOARD_LENGTH + 56,
      BOARD_LENGTH + 56,
      6,
    );
    graphics.fillStyle(COLORS.board, 1);
    graphics.fillRect(BOARD_MARGIN, BOARD_MARGIN, BOARD_LENGTH, BOARD_LENGTH);

    graphics.lineStyle(1, COLORS.grid, 0.92);
    for (let index = 0; index <= state.size; index += 1) {
      const horizontalStart = this.point(state.size, index, 0);
      const horizontalEnd = this.point(state.size, index, state.size);
      graphics.lineBetween(
        horizontalStart.x,
        horizontalStart.y,
        horizontalEnd.x,
        horizontalEnd.y,
      );
      const verticalStart = this.point(state.size, 0, index);
      const verticalEnd = this.point(state.size, state.size, index);
      graphics.lineBetween(verticalStart.x, verticalStart.y, verticalEnd.x, verticalEnd.y);
    }

    graphics.lineStyle(2, COLORS.boundary, 1);
    graphics.strokeRect(BOARD_MARGIN, BOARD_MARGIN, BOARD_LENGTH, BOARD_LENGTH);
    this.drawTargetEdges(graphics, state);
    this.drawWalls(graphics, state);
    this.drawPoints(graphics, state);

    if (!(state.outcome.status === "won" && state.outcome.reason === "escaped")) {
      const step = BOARD_LENGTH / state.size;
      const ballX = BOARD_MARGIN + (state.ball.col + 0.5) * step;
      const ballY = BOARD_MARGIN + (state.ball.row + 0.5) * step;
      graphics.fillStyle(COLORS.accent, 1);
      graphics.fillCircle(ballX, ballY, Math.max(11, step * 0.29));
      graphics.lineStyle(3, COLORS.white, 0.88);
      graphics.strokeCircle(ballX, ballY, Math.max(11, step * 0.29));
    }

    if (highlightedAction !== null) {
      const width = state.size + 1;
      const row = Math.floor(highlightedAction / width);
      const col = highlightedAction % width;
      const selected = this.point(state.size, row, col);
      graphics.lineStyle(4, COLORS.accent, 1);
      const markerRadius = Math.min(24, Math.max(14, BOARD_LENGTH / state.size / 2.8));
      graphics.strokeCircle(selected.x, selected.y, markerRadius);
    }
  }

  private drawTargetEdges(graphics: Phaser.GameObjects.Graphics, state: BoardState): void {
    if (state.outcome.status !== "playing") return;
    const edges =
      state.turn === "white"
        ? [
            [BOARD_MARGIN, BOARD_MARGIN, BOARD_MARGIN, BOARD_MARGIN + BOARD_LENGTH],
            [
              BOARD_MARGIN + BOARD_LENGTH,
              BOARD_MARGIN,
              BOARD_MARGIN + BOARD_LENGTH,
              BOARD_MARGIN + BOARD_LENGTH,
            ],
          ]
        : [
            [BOARD_MARGIN, BOARD_MARGIN, BOARD_MARGIN + BOARD_LENGTH, BOARD_MARGIN],
            [
              BOARD_MARGIN,
              BOARD_MARGIN + BOARD_LENGTH,
              BOARD_MARGIN + BOARD_LENGTH,
              BOARD_MARGIN + BOARD_LENGTH,
            ],
          ];
    for (const [x1, y1, x2, y2] of edges) {
      graphics.lineStyle(20, COLORS.target, 0.1);
      graphics.lineBetween(x1, y1, x2, y2);
      graphics.lineStyle(3, COLORS.target, 0.9);
      graphics.lineBetween(x1, y1, x2, y2);
    }
  }

  private drawWalls(graphics: Phaser.GameObjects.Graphics, state: BoardState): void {
    for (const wall of state.walls) {
      const start = this.point(state.size, wall.row, wall.col);
      const end = this.point(
        state.size,
        wall.row + (wall.orientation === "vertical" ? 1 : 0),
        wall.col + (wall.orientation === "horizontal" ? 1 : 0),
      );
      if (wall.color === "white") {
        graphics.lineStyle(12, COLORS.whiteOutline, 0.9);
        graphics.lineBetween(start.x, start.y, end.x, end.y);
        graphics.lineStyle(7, COLORS.white, 1);
      } else {
        graphics.lineStyle(11, COLORS.blackOutline, 0.75);
        graphics.lineBetween(start.x, start.y, end.x, end.y);
        graphics.lineStyle(7, COLORS.black, 1);
      }
      graphics.lineBetween(start.x, start.y, end.x, end.y);
    }
  }

  private drawPoints(graphics: Phaser.GameObjects.Graphics, state: BoardState): void {
    const pointRadius = Math.max(4.5, BOARD_LENGTH / state.size / 8);
    for (let row = 0; row <= state.size; row += 1) {
      for (let col = 0; col <= state.size; col += 1) {
        const point = this.point(state.size, row, col);
        const post = state.posts[row * (state.size + 1) + col];
        if (post === "W") {
          this.drawPost(graphics, point, "white", pointRadius);
        } else if (post === "B") {
          this.drawPost(graphics, point, "black", pointRadius);
        } else {
          graphics.fillStyle(COLORS.board, 1);
          graphics.fillCircle(point.x, point.y, pointRadius * 0.48);
          graphics.lineStyle(1.4, COLORS.emptyPoint, 1);
          graphics.strokeCircle(point.x, point.y, pointRadius * 0.48);
        }
      }
    }
  }

  private drawPost(
    graphics: Phaser.GameObjects.Graphics,
    point: Phaser.Math.Vector2,
    player: Player,
    radius: number,
  ): void {
    const isWhite = player === "white";
    graphics.fillStyle(isWhite ? COLORS.white : COLORS.black, 1);
    graphics.fillCircle(point.x, point.y, radius);
    graphics.lineStyle(2, isWhite ? COLORS.whiteOutline : COLORS.blackOutline, 1);
    graphics.strokeCircle(point.x, point.y, radius);
  }
}

export const BOARD_CANVAS_SIZE = CANVAS_SIZE;
