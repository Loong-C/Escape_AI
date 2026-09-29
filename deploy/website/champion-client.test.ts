import { afterEach, describe, expect, it, vi } from "vitest";
import { createGame } from "../src/game";
import { checkChampionHealth, requestChampionMove } from "../src/ai/champion-client";

const reply = { move: { row: 6, col: 8, kind: "place" },
  stats: { nodes: 512, score: 0, depth: 0, elapsedMs: 500, candidates: 324 } };

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("champion HTTP requests", () => {
  it.each([503, 502, 504])("reports an unavailable server for HTTP %s", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status })));
    await expect(requestChampionMove(createGame(), 1, new AbortController().signal)).rejects.toThrow("服务器不可用");
  });

  it("requires a ready CUDA backend before starting AI play", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ enabled: true, model: { device: "cpu" } })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ enabled: true, model: { device: "cuda" } })))
      .mockRejectedValueOnce(new TypeError("network down")));
    expect(await checkChampionHealth()).toBe(false);
    expect(await checkChampionHealth()).toBe(true);
    expect(await checkChampionHealth()).toBe(false);
  });

  it("returns a legal-shaped response without a Worker or AbortSignal.timeout", async () => {
    vi.stubGlobal("Worker", undefined);
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(reply)));
    vi.stubGlobal("fetch", fetcher);
    expect(await requestChampionMove(createGame(), 1, new AbortController().signal)).toEqual(reply);
    expect(JSON.parse(fetcher.mock.calls[0][1].body).posts).toHaveLength(324);
  });

  it.each(["connection", "response body"])("bounds a stalled %s even if fetch ignores abort", async (stage) => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", stage === "connection"
      ? vi.fn(() => new Promise(() => {}))
      : vi.fn().mockResolvedValue({ ok: true, json: () => new Promise(() => {}) }));
    const pending = requestChampionMove(createGame(), 1, new AbortController().signal);
    const assertion = expect(pending).rejects.toThrow("服务器不可用");
    await vi.advanceTimersByTimeAsync(30_000);
    await assertion;
    expect(vi.getTimerCount()).toBe(0);
  });

  it("cancels an abandoned game promptly", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    const controller = new AbortController();
    const pending = requestChampionMove(createGame(), 1, controller.signal);
    controller.abort();
    await expect(pending).rejects.toThrow("AI 请求已取消");
  });

  it("never sends an already cancelled request", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const controller = new AbortController();
    controller.abort();
    await expect(requestChampionMove(createGame(), 1, controller.signal)).rejects.toThrow("已取消");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("reports a busy service, then permits a successful retry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response("{}", { status: 429 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(reply))));
    await expect(requestChampionMove(createGame(), 1, new AbortController().signal)).rejects.toThrow("正忙");
    expect(await requestChampionMove(createGame(), 2, new AbortController().signal)).toEqual(reply);
  });

  it("rejects out-of-board replies", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ...reply, move: { row: 99, col: 8, kind: "place" },
    }))));
    await expect(requestChampionMove(createGame(), 1, new AbortController().signal)).rejects.toThrow("无效结果");
  });
});
