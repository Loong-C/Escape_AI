import { useMemo, useState } from "react";
import type { AiDifficulty } from "../ai";
import { getNeighborEscapeDistances, previewMove, type Move, type MovePreview } from "../game";
import {
  TUTORIAL_LABELS,
  completeTutorialMove,
  createTutorialLessons,
  type TutorialLesson,
} from "../tutorial/lessons";
import { LazyBoardCanvas } from "./LazyBoardCanvas";

interface TutorialScreenProps {
  onHome: () => void;
  onStartMatch: (difficulty: AiDifficulty) => void;
}

const SUCCESS_MESSAGES: Record<TutorialLesson["label"], string> = {
  放置桩: "这枚桩尚未连接墙，所以它是浮桩。",
  形成墙: "墙已经形成，两枚白桩现在都是锚桩。",
  替换浮桩: "黑色浮桩已被白桩替换，并与左侧白桩形成了墙。",
  最短路径长度: "上方从 8 变为 ∞；右、下、左仍是 8。三个方向并列最短，球留在原地。",
  推动球: "落桩后，上方从 3 变为 ∞，右侧的 3 成为唯一最小值。球向右移动一格；棋盘数字随后以球的新位置重新计算。",
  边界胜负: "球从右边界离开。左右边界属于白方，所以这一局由白方获胜。",
  封闭胜负: "四面墙已经封闭。落下最后一枚桩的白方立即获胜。",
};

export function TutorialScreen({ onHome, onStartMatch }: TutorialScreenProps) {
  const lessons = useMemo(createTutorialLessons, []);
  const [lessonIndex, setLessonIndex] = useState(0);
  const lesson = lessons[lessonIndex];
  const [state, setState] = useState(lesson.initialState);
  const [focusedMove, setFocusedMove] = useState<Move | null>(null);
  const [completed, setCompleted] = useState(false);
  const [completionPreview, setCompletionPreview] = useState<MovePreview | null>(null);

  function handleSelect(move: Move): void {
    if (completed) return;
    const movePreview = previewMove(state, move);
    const result = completeTutorialMove(lesson, state, move, movePreview);
    if (!result) return;
    setState(result.state);
    setCompletionPreview(result.preview);
    setFocusedMove(null);
    setCompleted(true);
  }

  function continueTutorial(): void {
    if (!completed) return;
    if (lessonIndex === lessons.length - 1) {
      onStartMatch("easy");
      return;
    }
    const nextIndex = lessonIndex + 1;
    setLessonIndex(nextIndex);
    setState(lessons[nextIndex].initialState);
    setFocusedMove(null);
    setCompleted(false);
    setCompletionPreview(null);
  }

  function replayLesson(): void {
    setState(lesson.initialState);
    setFocusedMove(null);
    setCompleted(false);
    setCompletionPreview(null);
  }

  const directions = ["up", "right", "down", "left"] as const;
  const names = { up: "上", right: "右", down: "下", left: "左" };
  const format = (value: number) => Number.isFinite(value) ? String(value) : "∞";

  return (
    <main id="main-content" className="game-layout tutorial-layout" tabIndex={-1}>
      <section className="playfield-region">
        <LazyBoardCanvas
          state={state}
          key={lessonIndex}
          focusedMove={completed ? null : focusedMove}
          tutorialTarget={completed ? null : lesson.target}
          goalPlayer={lesson.initialState.turn}
          distanceHints={
            lesson.showDistances && state.outcome.reason !== "escaped"
              ? { distances: getNeighborEscapeDistances(state) }
              : null
          }
          highlightShortestDistances={lesson.showDistances}
          interactive={!completed}
          canSelect={(move) =>
            !completed && move.row === lesson.target.row && move.col === lesson.target.col
          }
          onHover={(move) => setFocusedMove(move)}
          onSelect={handleSelect}
        />
      </section>

      <aside className="side-rail tutorial-rail">
        <div className="tutorial-heading-row">
          <span>{lesson.label}</span>
          <strong>{lessonIndex + 1} / {lessons.length}</strong>
        </div>
        <div className="tutorial-copy">
          <h1>{lesson.title}</h1>
          <p>{lesson.description}</p>
          <p className="tutorial-instruction">{lesson.instruction}</p>
        </div>

        {lesson.showDistances && (
          <section aria-label="数字变化" className="tutorial-copy">
            <p>{completed
              ? state.outcome.reason === "escaped" ? "球已出界，棋盘不再显示数字。" : "棋盘显示：球当前位置的数字。"
              : "棋盘显示：落子前的当前数字。悬停不会改变数字。"}</p>
            {completionPreview && (
              <>
                <p>对照球移动前的同一个位置：</p>
                <table style={{ width: "100%", textAlign: "center" }}>
                  <thead><tr><th scope="col">方向</th><th scope="col">落桩前</th><th scope="col">落桩后</th></tr></thead>
                  <tbody>{directions.map(direction => (
                    <tr key={direction}><th scope="row">{names[direction]}</th>
                      <td>{format(completionPreview.before[direction])}</td>
                      <td>{format(completionPreview.afterPlacement[direction])}</td></tr>
                  ))}</tbody>
                </table>
              </>
            )}
          </section>
        )}

        {(lesson.label === "形成墙" || lesson.label === "替换浮桩") && (
          <div className="post-legend" aria-label="桩的状态图例">
            <span><i className="post-symbol post-symbol--float" />浮桩</span>
            <span><i className="post-symbol post-symbol--anchor" />锚桩</span>
          </div>
        )}

        <div className="tutorial-feedback" aria-live="polite">
          {completed ? SUCCESS_MESSAGES[lesson.label] : "完成棋盘上的蓝色目标后继续。"}
        </div>

        <div className="tutorial-actions">
          <button
            className="primary-button"
            type="button"
            disabled={!completed}
            onClick={continueTutorial}
          >
            {lessonIndex === lessons.length - 1 ? "开始人机对战" : "继续"}
          </button>
          {completed && <button className="secondary-button" type="button" onClick={replayLesson}>再试一次</button>}
          <button className="secondary-button" type="button" onClick={onHome}>
            退出教程
          </button>
        </div>

        <ol className="tutorial-progress" aria-label="教程进度"
          style={{ gridTemplateColumns: `repeat(${lessons.length}, 1fr)` }}>
          {TUTORIAL_LABELS.map((label, index) => (
            <li
              key={label}
              className={index <= lessonIndex ? "is-active" : ""}
              aria-current={index === lessonIndex ? "step" : undefined}
            >
              <span aria-hidden="true" />
              {label}
            </li>
          ))}
        </ol>
      </aside>
    </main>
  );
}
