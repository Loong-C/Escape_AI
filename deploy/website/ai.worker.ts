/// <reference lib="webworker" />

import type { AiMoveRequest, AiWorkerResponse, AiMoveResponse } from "./messages";

self.onmessage = async (event: MessageEvent<AiMoveRequest>) => {
  const request = event.data;
  if (request.type !== "choose-move") return;
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}api/champion/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        posts: request.state.posts,
        ball: request.state.ball,
        turn: request.state.turn,
        seed: (request.state.moveNumber * 65_537 + request.requestId) >>> 0,
      }),
      signal: AbortSignal.timeout(90_000),
    });
    if (!response.ok) {
      throw new Error(response.status === 429 || response.status === 503
        ? "冠军 AI 正忙，请稍后重试。"
        : "冠军 AI 暂时无法连接，请稍后重试。");
    }
    const result = await response.json() as Pick<AiMoveResponse, "move" | "stats">;
    if (!result.move || !Number.isInteger(result.move.row) || !Number.isInteger(result.move.col)
        || !result.stats || result.stats.nodes !== 512) {
      throw new Error("冠军 AI 返回了无效结果，请重试。");
    }
    const message: AiWorkerResponse = {
      type: "move-result", requestId: request.requestId,
      move: result.move, stats: result.stats,
    };
    self.postMessage(message);
  } catch (error) {
    const message: AiWorkerResponse = {
      type: "move-error", requestId: request.requestId,
      message: error instanceof Error ? error.message : "AI 计算失败",
    };
    self.postMessage(message);
  }
};

export {};
