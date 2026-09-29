/// <reference types="vite/client" />

import type { GameState, LegalMove } from "../game";
import type { SearchResult } from "./search";

export interface ChampionReply {
  move: LegalMove;
  stats: Omit<SearchResult, "move">;
}

export const AI_REQUEST_CANCELLED = "AI 请求已取消";

export async function checkChampionHealth(): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 4000);
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}api/champion/health`, {
      signal: controller.signal, cache: "no-store",
    });
    if (!response.ok) return false;
    const result = await response.json() as { enabled?: boolean; model?: { device?: string } } | null;
    return result?.enabled === true && result.model?.device === "cuda";
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

export async function requestChampionMove(
  state: GameState,
  requestId: number,
  signal: AbortSignal,
  timeoutMs = 30_000,
): Promise<ChampionReply> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let cancel = () => {};
  const deadline = new Promise<never>((_resolve, reject) => {
    cancel = () => {
      reject(new Error(AI_REQUEST_CANCELLED));
      controller.abort();
    };
    signal.addEventListener("abort", cancel, { once: true });
    timer = setTimeout(() => {
      reject(new Error("服务器不可用"));
      controller.abort();
    }, timeoutMs);
  });
  try {
    if (signal.aborted) {
      cancel();
      return await deadline;
    }
    const request = (async (): Promise<ChampionReply> => {
      let response: Response;
      try {
        response = await fetch(`${import.meta.env.BASE_URL}api/champion/move`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            posts: state.posts,
            ball: state.ball,
            turn: state.turn,
            seed: (state.moveNumber * 65_537 + requestId) >>> 0,
          }),
          signal: controller.signal,
        });
      } catch {
        throw new Error("服务器不可用");
      }
      if (!response.ok) {
        throw new Error(response.status === 429
          ? "冠军 AI 正忙，请稍后重试。"
          : "服务器不可用");
      }
      const result = await response.json() as ChampionReply | null;
      if (!result?.move || !Number.isInteger(result.move.row)
          || !Number.isInteger(result.move.col) || result.move.row < 0
          || result.move.row > state.size || result.move.col < 0
          || result.move.col > state.size
          || !["place", "replace"].includes(result.move.kind)
          || !result.stats || result.stats.nodes !== 512) {
        throw new Error("冠军 AI 返回了无效结果，请重试。");
      }
      return result;
    })();
    return await Promise.race([request, deadline]);
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", cancel);
  }
}
