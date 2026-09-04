import type { GameSummary, ResearchGame } from "./types";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`请求失败（HTTP ${response.status}）`);
  }
  return (await response.json()) as T;
}

export function listGames(): Promise<GameSummary[]> {
  return request<GameSummary[]>("/api/games?limit=1000");
}

export function loadGame(gameId: string): Promise<ResearchGame> {
  return request<ResearchGame>(`/api/games/${encodeURIComponent(gameId)}`);
}
