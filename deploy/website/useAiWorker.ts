import { useCallback, useEffect, useRef } from "react";
import type { GameState } from "../game";
import type { AiDifficulty } from "../ai";
import { requestChampionMove, type ChampionReply } from "../ai/champion-client";

export type AiTurnResult = ChampionReply;

// Keep the existing hook's interface; server inference needs no browser Worker.
export function useAiWorker(enabled = true) {
  const nextRequestId = useRef(1);
  const pending = useRef(new Set<AbortController>());

  useEffect(() => {
    const requests = pending.current;
    return () => {
      for (const controller of requests) controller.abort();
      requests.clear();
    };
  }, [enabled]);

  return useCallback((state: GameState, _difficulty: AiDifficulty) => {
    if (!enabled) return Promise.reject(new Error("当前对局未启用 AI。"));
    for (const previous of pending.current) previous.abort();
    const controller = new AbortController();
    pending.current.add(controller);
    return requestChampionMove(state, nextRequestId.current++, controller.signal)
      .finally(() => pending.current.delete(controller));
  }, [enabled]);
}
