import type {
  GameSummary,
  PlayConfiguration,
  PlayGame,
  Player,
  ResearchGame,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `请求失败（HTTP ${response.status}）`);
  }
  return (await response.json()) as T;
}

export function listGames(): Promise<GameSummary[]> {
  return request<GameSummary[]>("/api/games?limit=1000");
}

export function loadGame(gameId: string): Promise<ResearchGame> {
  return request<ResearchGame>(`/api/games/${encodeURIComponent(gameId)}`);
}

export function loadPlayConfiguration(): Promise<PlayConfiguration> {
  return request<PlayConfiguration>("/api/play");
}

export function createPlayGame(humanPlayer: Player): Promise<PlayGame> {
  return request<PlayGame>("/api/play/games", {
    method: "POST",
    body: JSON.stringify({ human_player: humanPlayer }),
  });
}

export function loadPlayGame(sessionId: string): Promise<PlayGame> {
  return request<PlayGame>(`/api/play/games/${encodeURIComponent(sessionId)}`);
}

export function playHumanMove(sessionId: string, action: number): Promise<PlayGame> {
  return request<PlayGame>(`/api/play/games/${encodeURIComponent(sessionId)}/moves`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });
}
