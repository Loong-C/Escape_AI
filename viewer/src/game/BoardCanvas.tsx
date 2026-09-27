import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Phaser from "phaser";

import type { BoardState } from "../types";
import { BOARD_CANVAS_SIZE, BoardScene } from "./BoardScene";

interface BoardCanvasProps {
  state: BoardState;
  highlightedAction: number | null;
  legalActions?: readonly number[];
  disabled?: boolean;
  onAction?: (action: number) => void;
}

const BOARD_MARGIN = 94;
const BOARD_LENGTH = BOARD_CANVAS_SIZE - BOARD_MARGIN * 2;

export function BoardCanvas({
  state,
  highlightedAction,
  legalActions = [],
  disabled = false,
  onAction,
}: BoardCanvasProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<BoardScene | null>(null);
  const gameRef = useRef<Phaser.Game | null>(null);
  const [hoveredAction, setHoveredAction] = useState<number | null>(null);
  const legalSet = useMemo(() => new Set(legalActions), [legalActions]);

  useEffect(() => {
    if (!hostRef.current) return;
    const scene = new BoardScene();
    sceneRef.current = scene;
    gameRef.current = new Phaser.Game({
      type: Phaser.AUTO,
      parent: hostRef.current,
      width: BOARD_CANVAS_SIZE,
      height: BOARD_CANVAS_SIZE,
      backgroundColor: "#15181c",
      scene,
      render: { antialias: true, roundPixels: true },
      scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
      audio: { noAudio: true },
    });
    return () => {
      gameRef.current?.destroy(true);
      gameRef.current = null;
      sceneRef.current = null;
    };
  }, []);

  useEffect(() => {
    sceneRef.current?.setView({ state, highlightedAction, hoveredAction, legalActions });
  }, [state, highlightedAction, hoveredAction, legalActions]);

  const actionAt = useCallback((clientX: number, clientY: number): number | null => {
    const bounds = hostRef.current?.getBoundingClientRect();
    if (!bounds || disabled || !onAction) return null;
    const x = ((clientX - bounds.left) / bounds.width) * BOARD_CANVAS_SIZE;
    const y = ((clientY - bounds.top) / bounds.height) * BOARD_CANVAS_SIZE;
    const step = BOARD_LENGTH / state.size;
    const col = Math.round((x - BOARD_MARGIN) / step);
    const row = Math.round((y - BOARD_MARGIN) / step);
    if (row < 0 || row > state.size || col < 0 || col > state.size) return null;
    const pointX = BOARD_MARGIN + col * step;
    const pointY = BOARD_MARGIN + row * step;
    if (Math.hypot(x - pointX, y - pointY) > step * 0.42) return null;
    const action = row * (state.size + 1) + col;
    return legalSet.has(action) ? action : null;
  }, [disabled, legalSet, onAction, state.size]);

  return (
    <div
      className={`board-canvas ${hoveredAction !== null ? "is-actionable" : ""}`}
      ref={hostRef}
      role={onAction ? "grid" : undefined}
      aria-label={onAction ? "Escape 可交互棋盘；点击带蓝色圆环的合法着点" : undefined}
      aria-hidden={onAction ? undefined : true}
      onPointerMove={(event) => setHoveredAction(actionAt(event.clientX, event.clientY))}
      onPointerLeave={() => setHoveredAction(null)}
      onPointerUp={(event) => {
        const action = actionAt(event.clientX, event.clientY);
        if (action !== null) onAction?.(action);
      }}
    />
  );
}
