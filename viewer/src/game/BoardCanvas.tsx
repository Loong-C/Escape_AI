import { useEffect, useRef } from "react";
import Phaser from "phaser";

import type { BoardState } from "../types";
import { BOARD_CANVAS_SIZE, BoardScene } from "./BoardScene";

interface BoardCanvasProps {
  state: BoardState;
  highlightedAction: number | null;
}

export function BoardCanvas({ state, highlightedAction }: BoardCanvasProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<BoardScene | null>(null);
  const gameRef = useRef<Phaser.Game | null>(null);

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
    sceneRef.current?.setView({ state, highlightedAction });
  }, [state, highlightedAction]);

  return <div className="board-canvas" ref={hostRef} aria-hidden="true" />;
}
