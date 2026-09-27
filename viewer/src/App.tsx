import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createPlayGame,
  listGames,
  loadGame,
  loadPlayConfiguration,
  playHumanMove,
} from "./api";
import { actionName, outcomeText, playerName, signed } from "./format";
import { BoardCanvas } from "./game/BoardCanvas";
import type {
  BoardState,
  Candidate,
  GameSummary,
  PlayConfiguration,
  PlayGame,
  Player,
  ResearchGame,
  ResearchMove,
} from "./types";

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
      {badges.map((badge) => <span key={badge}>{badge}</span>)}
    </div>
  );
}

function CandidateList({
  candidates,
  size,
  title = "搜索候选",
}: {
  candidates: Candidate[];
  size: number;
  title?: string;
}) {
  const maxVisits = Math.max(1, ...candidates.map((candidate) => candidate.visits));
  return (
    <section className="panel candidate-panel">
      <div className="section-heading">
        <h2>{title}</h2>
        <span>访问 / Q</span>
      </div>
      <div className="candidate-list">
        {candidates.slice(0, 8).map((candidate, index) => (
          <div className="candidate" key={candidate.action}>
            <div className="candidate-line">
              <strong>{index + 1}. {actionName(candidate.action, size)}</strong>
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
        <span /><strong>白</strong><strong>黑</strong>
        <span>桩</span><b>{features.white_posts}</b><b>{features.black_posts}</b>
        <span>浮桩</span><b>{features.white_floating}</b><b>{features.black_floating}</b>
        <span>锚桩</span><b>{features.white_anchored}</b><b>{features.black_anchored}</b>
        <span>墙</span><b>{features.white_walls}</b><b>{features.black_walls}</b>
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
        <input type="range" min="0" max={max} value={index} onChange={(event) => onIndex(Number(event.target.value))} />
      </label>
      <small>←/→ 单步 · 空格 播放或暂停</small>
    </section>
  );
}

function HumanPlay({ configuration }: { configuration: PlayConfiguration }) {
  const [game, setGame] = useState<PlayGame | null>(null);
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startGame = useCallback(async (humanPlayer: Player) => {
    setThinking(true);
    setError(null);
    try {
      setGame(await createPlayGame(humanPlayer));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法创建对局");
    } finally {
      setThinking(false);
    }
  }, []);

  useEffect(() => { void startGame("white"); }, [startGame]);

  const submitAction = useCallback(async (action: number) => {
    if (!game || thinking || !game.legal_actions.includes(action)) return;
    setThinking(true);
    setError(null);
    try {
      setGame(await playHumanMove(game.session_id, action));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "落子失败");
    } finally {
      setThinking(false);
    }
  }, [game, thinking]);

  const lastMove = game?.moves.at(-1) ?? null;
  const lastAiMove = game
    ? [...game.moves].reverse().find((move) => move.actor === "ai") ?? null
    : null;
  const state = game?.state ?? null;
  const isTerminal = state?.outcome.status !== "playing";
  const status = !state
    ? "正在建立对局…"
    : thinking
      ? "冠军 AI 正在搜索…"
      : isTerminal
        ? outcomeText(state.outcome)
        : `${playerName(state.turn)}回合 · 点击蓝圈落子`;

  return (
    <main className="viewer-layout play-layout">
      <section className="playfield" aria-label="Escape 人机对战棋盘">
        {state ? (
          <div className="board-shell is-interactive">
            <BoardCanvas
              state={state}
              highlightedAction={lastMove?.action ?? null}
              legalActions={thinking ? [] : game?.legal_actions}
              disabled={thinking || isTerminal}
              onAction={(action) => void submitAction(action)}
            />
            {thinking && <div className="thinking-overlay"><span /><strong>AI SEARCHING</strong><small>{game?.model.simulations ?? configuration.model?.simulations ?? 512} 次 PUCT · D4 八视角</small></div>}
            <div className="board-caption">
              <span>17 × 17 · SERVER RULES</span>
              <strong>{status}</strong>
            </div>
          </div>
        ) : (
          <div className="empty-board">{thinking ? "正在加载冠军模型…" : "尚未开始"}</div>
        )}
        <div className="play-hint">蓝色细圈为合法着点；落子后由服务器核验规则并计算 AI 回手。</div>
      </section>

      <aside className="analysis-rail" aria-label="人机对战信息">
        <section className="play-intro">
          <span className="eyebrow">VERIFIED CHAMPION</span>
          <h1>挑战 Escape AI</h1>
          <p>谱系 C 第 199 代 · 角色感知 D4 集成</p>
          <div className="side-selector" aria-label="选择执子颜色">
            <button type="button" className={game?.human_player === "white" ? "active" : ""} onClick={() => void startGame("white")} disabled={thinking}>执白新局</button>
            <button type="button" className={game?.human_player === "black" ? "active" : ""} onClick={() => void startGame("black")} disabled={thinking}>执黑新局</button>
          </div>
        </section>

        {error && <div className="error-box" role="alert">{error}</div>}
        {game && state && (
          <>
            <section className="position-lead play-position">
              <div>
                <span>PLY {game.moves.length + 1}</span>
                <h1>{status}</h1>
              </div>
              {lastAiMove?.root_value !== null && lastAiMove && (
                <div className={`value-orb ${lastAiMove.root_value < 0 ? "is-negative" : ""}`}>
                  <span>AI VALUE</span><strong>{signed(lastAiMove.root_value)}</strong>
                </div>
              )}
            </section>
            <div className="micro-metrics play-metrics">
              <div><span>你</span><strong>{playerName(game.human_player)}</strong></div>
              <div><span>AI</span><strong>{playerName(game.ai_player)}</strong></div>
              <div><span>模拟/手</span><strong>{game.model.simulations}</strong></div>
              <div><span>上手耗时</span><strong>{lastAiMove?.elapsed_ms ? `${(lastAiMove.elapsed_ms / 1000).toFixed(1)}s` : "—"}</strong></div>
            </div>
            {isTerminal && (
              <section className="result-panel">
                <span>GAME OVER</span>
                <h1>{outcomeText(state.outcome)}</h1>
                <p>共 {game.moves.length} 手。可立即选择颜色再来一局。</p>
              </section>
            )}
            {lastAiMove && <CandidateList candidates={lastAiMove.candidates} size={state.size} title="AI 上手搜索" />}
            <section className="panel model-card">
              <div className="section-heading"><h2>模型凭证</h2><span>已验证最强版本</span></div>
              <dl>
                <div><dt>Checkpoint</dt><dd>{game.model.checkpoint_sha256.slice(0, 16)}…</dd></div>
                <div><dt>Evaluator</dt><dd>D4 ensemble</dd></div>
                <div><dt>PUCT</dt><dd>c={game.model.c_puct} · leaves {game.model.parallel_leaves}</dd></div>
                <div><dt>Device</dt><dd>{game.model.device.toUpperCase()}</dd></div>
              </dl>
            </section>
            <section className="panel move-log">
              <div className="section-heading"><h2>着法记录</h2><span>{game.moves.length} 手</span></div>
              {game.moves.length ? (
                <ol>
                  {game.moves.slice(-12).map((move) => (
                    <li key={move.ply}>
                      <span>{move.ply + 1}</span>
                      <strong>{move.actor === "ai" ? "AI" : "你"} · {actionName(move.action, state.size)}</strong>
                      <small>{move.move_kind === "replacement" ? "替换" : "落桩"}</small>
                    </li>
                  ))}
                </ol>
              ) : <p>等待你的第一手。</p>}
            </section>
          </>
        )}
        {!game && configuration.model && (
          <section className="result-panel"><span>MODEL READY</span><h1>{configuration.model.name}</h1></section>
        )}
      </aside>
    </main>
  );
}

function ResearchViewer() {
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
      setGame(await loadGame(gameId));
      setFrameIndex(0);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取棋谱");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    listGames().then((items) => {
      if (!active) return;
      setSummaries(items);
      if (items[0]) return selectGame(items[0].game_id);
      setLoading(false);
    }).catch((reason: unknown) => {
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
        ) : <div className="empty-board">{loading ? "正在解码棋谱…" : "没有可显示的棋谱"}</div>}
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
              <div><span>PLY {currentMove.ply + 1}</span><h1>{playerName(currentMove.turn)}思考</h1></div>
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
            <CandidateList candidates={currentMove.candidates} size={state.size} />
            <StructurePanel move={currentMove} />
          </>
        )}
        {!currentMove && game && state && (
          <section className="result-panel"><span>FINAL POSITION</span><h1>{outcomeText(state.outcome)}</h1><p>共 {game.moves.length} 手 · {game.search_simulations.toLocaleString()} 次模拟/手</p></section>
        )}
      </aside>
    </main>
  );
}

export default function App() {
  const [mode, setMode] = useState<"play" | "research">("play");
  const [configuration, setConfiguration] = useState<PlayConfiguration | null>(null);

  useEffect(() => {
    let active = true;
    loadPlayConfiguration().then((value) => {
      if (!active) return;
      setConfiguration(value);
      if (!value.enabled) setMode("research");
    }).catch(() => {
      if (!active) return;
      setConfiguration({ enabled: false, model: null });
      setMode("research");
    });
    return () => { active = false; };
  }, []);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <Logo />
          <div><strong>ESCAPE AI</strong><span>{mode === "play" ? "PLAY THE CHAMPION" : "RESEARCH VIEWER"}</span></div>
        </div>
        <nav className="mode-switch" aria-label="页面模式">
          <button type="button" className={mode === "play" ? "active" : ""} onClick={() => setMode("play")} disabled={!configuration?.enabled}>人机对战</button>
          <button type="button" className={mode === "research" ? "active" : ""} onClick={() => setMode("research")}>研究棋谱</button>
        </nav>
        <div className={`dataset-status ${configuration?.enabled ? "" : "is-offline"}`}><span />{configuration === null ? "正在连接" : configuration.enabled ? "冠军在线" : "只读模式"}</div>
      </header>
      {configuration === null ? (
        <main className="loading-screen"><span /><strong>正在连接 Escape AI…</strong></main>
      ) : mode === "play" && configuration.enabled ? (
        <HumanPlay configuration={configuration} />
      ) : (
        <ResearchViewer />
      )}
    </div>
  );
}
