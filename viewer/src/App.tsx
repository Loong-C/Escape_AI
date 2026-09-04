import { useCallback, useEffect, useMemo, useState } from "react";

import { listGames, loadGame } from "./api";
import { actionName, outcomeText, playerName, signed } from "./format";
import { BoardCanvas } from "./game/BoardCanvas";
import type { BoardState, GameSummary, ResearchGame, ResearchMove } from "./types";

const DIRECTIONS = ["上", "右", "下", "左"];

function Logo() {
  return (
    <svg className="brand-mark" viewBox="0 0 40 32" aria-hidden="true">
      <path d="M4 6h32M4 16h32M4 26h32M8 2v28M20 2v28M32 2v28" />
      <circle cx="20" cy="16" r="5" />
    </svg>
  );
}

function TacticalBadges({ move }: { move: ResearchMove }) {
  const badges: string[] = [];
  if (move.features.reply_resistance !== null && move.features.reply_resistance <= 1) {
    badges.push(`R=${move.features.reply_resistance} 强制`);
  }
  if (move.move_kind === "replacement") badges.push("替换战术");
  if (move.features.ball_moved) {
    badges.push(`球移动${move.features.ball_move_direction ? ` · ${move.features.ball_move_direction}` : ""}`);
  }
  if (move.features.unique_gradient) badges.push("唯一梯度");
  if (!badges.length) return null;
  return (
    <div className="badges" aria-label="战术标签">
      {badges.map((badge) => (
        <span key={badge}>{badge}</span>
      ))}
    </div>
  );
}

function CandidateList({ move, size }: { move: ResearchMove; size: number }) {
  const maxVisits = Math.max(1, ...move.candidates.map((candidate) => candidate.visits));
  return (
    <section className="panel candidate-panel">
      <div className="section-heading">
        <h2>搜索候选</h2>
        <span>访问 / Q</span>
      </div>
      <div className="candidate-list">
        {move.candidates.slice(0, 8).map((candidate, index) => (
          <div className="candidate" key={candidate.action}>
            <div className="candidate-line">
              <strong>
                {index + 1}. {actionName(candidate.action, size)}
              </strong>
              <span>{candidate.visits.toLocaleString()} · {signed(candidate.q)}</span>
            </div>
            <div className="candidate-track" aria-hidden="true">
              <span style={{ width: `${(candidate.visits / maxVisits) * 100}%` }} />
            </div>
            <small>P {candidate.prior.toFixed(3)}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function StructurePanel({ move }: { move: ResearchMove }) {
  const { features } = move;
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>局面结构</h2>
        <span>{features.legal_actions} 个合法着</span>
      </div>
      <div className="structure-grid">
        <span />
        <strong>白</strong>
        <strong>黑</strong>
        <span>桩</span>
        <b>{features.white_posts}</b>
        <b>{features.black_posts}</b>
        <span>浮桩</span>
        <b>{features.white_floating}</b>
        <b>{features.black_floating}</b>
        <span>锚桩</span>
        <b>{features.white_anchored}</b>
        <b>{features.black_anchored}</b>
        <span>墙</span>
        <b>{features.white_walls}</b>
        <b>{features.black_walls}</b>
      </div>
      <div className="distance-grid">
        {DIRECTIONS.map((direction, index) => (
          <div key={direction}>
            <span>{direction}</span>
            <strong>{features.directional_exit_distances[index]}</strong>
            <small>首步 {features.first_step_costs[index]}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

interface TimelineProps {
  index: number;
  max: number;
  playing: boolean;
  onIndex: (value: number) => void;
  onPlaying: (value: boolean) => void;
}

function Timeline({ index, max, playing, onIndex, onPlaying }: TimelineProps) {
  return (
    <section className="timeline" aria-label="棋谱时间轴">
      <div className="timeline-row">
        <button type="button" onClick={() => onIndex(0)} disabled={index === 0}>首局面</button>
        <button type="button" onClick={() => onIndex(Math.max(0, index - 1))} disabled={index === 0}>上一手</button>
        <button type="button" className="play-button" onClick={() => onPlaying(!playing)} disabled={max === 0}>
          {playing ? "暂停" : "播放"}
        </button>
        <button type="button" onClick={() => onIndex(Math.min(max, index + 1))} disabled={index === max}>下一手</button>
        <button type="button" onClick={() => onIndex(max)} disabled={index === max}>终局</button>
      </div>
      <label>
        <span>局面 {index} / {max}</span>
        <input
          type="range"
          min="0"
          max={max}
          value={index}
          onChange={(event) => onIndex(Number(event.target.value))}
        />
      </label>
      <small>←/→ 单步 · 空格 播放或暂停</small>
    </section>
  );
}

export default function App() {
  const [summaries, setSummaries] = useState<GameSummary[]>([]);
  const [game, setGame] = useState<ResearchGame | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectGame = useCallback(async (gameId: string) => {
    setLoading(true);
    setError(null);
    setPlaying(false);
    try {
      const selected = await loadGame(gameId);
      setGame(selected);
      setFrameIndex(0);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取棋谱");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    listGames()
      .then((items) => {
        if (!active) return;
        setSummaries(items);
        if (items[0]) return selectGame(items[0].game_id);
        setLoading(false);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "无法读取棋谱目录");
        setLoading(false);
      });
    return () => { active = false; };
  }, [selectGame]);

  const maxFrame = game?.moves.length ?? 0;
  useEffect(() => {
    if (!playing) return;
    if (frameIndex >= maxFrame) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => setFrameIndex((value) => value + 1), 700);
    return () => window.clearTimeout(timer);
  }, [playing, frameIndex, maxFrame]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return;
      if (event.key === "ArrowLeft") setFrameIndex((value) => Math.max(0, value - 1));
      if (event.key === "ArrowRight") setFrameIndex((value) => Math.min(maxFrame, value + 1));
      if (event.key === " ") {
        event.preventDefault();
        setPlaying((value) => !value);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [maxFrame]);

  const currentMove = game && frameIndex < game.moves.length ? game.moves[frameIndex] : null;
  const state: BoardState | null = useMemo(() => {
    if (!game) return null;
    return currentMove?.state ?? game.final_state;
  }, [game, currentMove]);
  const highlightedAction = currentMove?.action ?? (game?.moves.at(-1)?.action ?? null);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <Logo />
          <div><strong>ESCAPE AI</strong><span>RESEARCH VIEWER</span></div>
        </div>
        <div className="dataset-status"><span />{summaries.length} 局已索引</div>
      </header>

      <main className="viewer-layout">
        <section className="playfield" aria-label="Escape 棋盘">
          {state ? (
            <div className="board-shell">
              <BoardCanvas state={state} highlightedAction={highlightedAction} />
              <div className="board-caption">
                <span>{state.size} × {state.size}</span>
                <strong>{currentMove ? `${playerName(currentMove.turn)} · ${actionName(currentMove.action, state.size)}` : outcomeText(state.outcome)}</strong>
              </div>
            </div>
          ) : (
            <div className="empty-board">{loading ? "正在解码棋谱…" : "没有可显示的棋谱"}</div>
          )}
          {game && <Timeline index={frameIndex} max={maxFrame} playing={playing} onIndex={setFrameIndex} onPlaying={setPlaying} />}
        </section>

        <aside className="analysis-rail" aria-label="局面分析">
          <section className="game-picker">
            <label htmlFor="game-select">研究棋谱</label>
            <select id="game-select" value={game?.game_id ?? ""} onChange={(event) => void selectGame(event.target.value)} disabled={loading || !summaries.length}>
              {summaries.map((summary) => <option key={summary.game_id} value={summary.game_id}>{summary.game_id}</option>)}
            </select>
            {game && <p>{game.white_model_id} <span>vs</span> {game.black_model_id}</p>}
          </section>

          {error && <div className="error-box" role="alert">{error}</div>}
          {currentMove && state && (
            <>
              <section className="position-lead">
                <div>
                  <span>PLY {currentMove.ply + 1}</span>
                  <h1>{playerName(currentMove.turn)}思考</h1>
                </div>
                <div className={`value-orb ${currentMove.root_value < 0 ? "is-negative" : ""}`}>
                  <span>VALUE</span><strong>{signed(currentMove.root_value)}</strong>
                </div>
              </section>
              <TacticalBadges move={currentMove} />
              <div className="micro-metrics">
                <div><span>选择</span><strong>{actionName(currentMove.action, state.size)}</strong></div>
                <div><span>类型</span><strong>{currentMove.move_kind === "replacement" ? "替换" : "落桩"}</strong></div>
                <div><span>策略熵</span><strong>{currentMove.policy_entropy.toFixed(3)}</strong></div>
                <div><span>模拟</span><strong>{game?.search_simulations.toLocaleString()}</strong></div>
              </div>
              <CandidateList move={currentMove} size={state.size} />
              <StructurePanel move={currentMove} />
            </>
          )}
          {!currentMove && game && state && (
            <section className="result-panel">
              <span>FINAL POSITION</span>
              <h1>{outcomeText(state.outcome)}</h1>
              <p>共 {game.moves.length} 手 · {game.search_simulations.toLocaleString()} 次模拟/手</p>
            </section>
          )}
        </aside>
      </main>
    </div>
  );
}
