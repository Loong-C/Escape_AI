/// <reference types="vite/client" />

import type { GameState, LegalMove } from "../game";
import type { SearchResult } from "./search";

export interface ChampionReply {
  move: LegalMove;
  stats: Omit<SearchResult, "move">;
}

export const AI_REQUEST_CANCELLED = "AI 请求已取消";

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
      reject(new Error("AI 请求超过 30 秒，请检查网络后重试。"));
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
        throw new Error("暂时无法连接冠军 AI，请检查网络后重试。");
      }
      if (!response.ok) {
        throw new Error(response.status === 429 || response.status === 503
          ? "冠军 AI 正忙，请稍后重试。"
          : "冠军 AI 暂时无法连接，请稍后重试。");
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
