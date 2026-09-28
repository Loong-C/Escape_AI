import { describe, expect, it } from "vitest";
import { applyMove, getPost, getShortestEscapeInfo, getWallSegments, previewMove } from "../src/game";
import { completeTutorialMove, createTutorialLessons } from "../src/tutorial/lessons";

describe("Escape tutorial outcomes", () => {
  it("teaches a legal floating-post replacement that immediately forms a wall", () => {
    const lesson = createTutorialLessons()[2];
    const preview = previewMove(lesson.initialState, lesson.target);
    const result = completeTutorialMove(
      lesson,
      lesson.initialState,
      lesson.target,
      preview,
    );

    expect(lesson.label).toBe("替换浮桩");
    expect(getPost(lesson.initialState, 8, 8)).toBe("black");
    expect(preview?.move.kind).toBe("replace");
    expect(getPost(result!.state, 8, 8)).toBe("white");
    expect(getWallSegments(result!.state)).toContainEqual({
      orientation: "horizontal",
      row: 8,
      col: 7,
      color: "white",
    });
  });

  it("uses an effective distance example on the standard board", () => {
    const lesson = createTutorialLessons()[3];
    const preview = previewMove(lesson.initialState, lesson.target);

    expect(lesson.initialState.size).toBe(17);
    expect(preview?.before).toEqual({ up: 8, right: 8, down: 8, left: 8 });
    expect(preview?.afterPlacement).toEqual({ up: Infinity, right: 8, down: 8, left: 8 });
    expect(preview?.afterPlacement.up).toBe(Number.POSITIVE_INFINITY);
    expect(preview?.ballWillMove).toBeNull();
    expect(
      Object.entries(preview?.afterPlacement ?? {}).filter(
        ([direction, distance]) =>
          distance !== preview?.before[direction as keyof typeof preview.before],
      ),
    ).toEqual([
      ["up", Number.POSITIVE_INFINITY],
    ]);
  });

  it("forms a wall that leaves one shortest first step", () => {
    const lesson = createTutorialLessons()[4];
    const preview = previewMove(lesson.initialState, lesson.target);
    const result = completeTutorialMove(
      lesson,
      lesson.initialState,
      lesson.target,
      preview,
    );

    expect(lesson.initialState.size).toBe(17);
    expect(preview?.before.up).toBe(preview?.before.right);
    expect(preview?.afterPlacement.up).toBeGreaterThan(
      preview?.afterPlacement.right ?? Number.POSITIVE_INFINITY,
    );
    expect(preview?.shortestAfterPlacement.firstSteps).toEqual(["right"]);
    expect(preview?.before).toEqual({ up: 3, right: 3, down: 4, left: 4 });
    expect(preview?.afterPlacement).toEqual({ up: Infinity, right: 3, down: 4, left: 4 });
    expect(result?.state.ball).toEqual({ row: 3, col: 14 });
    expect(getWallSegments(result!.state)).toContainEqual({
      orientation: "horizontal",
      row: 3,
      col: 13,
      color: "white",
    });
  });

  it("requires closing the upper exit to cause a right-edge escape", () => {
    const lesson = createTutorialLessons()[5];
    const preview = previewMove(lesson.initialState, lesson.target);
    const result = completeTutorialMove(
      lesson,
      lesson.initialState,
      lesson.target,
      preview,
    );

    expect(lesson.initialState.size).toBe(17);
    expect(result?.state.outcome).toEqual({
      status: "won",
      winner: "white",
      reason: "escaped",
    });
    expect(result?.state.lastMove?.escapedThrough).toBe("right");
    expect(getShortestEscapeInfo(lesson.initialState).firstSteps).toEqual(["up", "right"]);
    const unrelated = applyMove(lesson.initialState, { row: 8, col: 8 });
    expect(unrelated.ball).toEqual(lesson.initialState.ball);
    expect(unrelated.outcome.status).toBe("playing");
    expect(preview?.before).toEqual({ up: 0, right: 0, down: 1, left: 1 });
    expect(preview?.afterPlacement).toEqual({ up: Infinity, right: 0, down: 1, left: 1 });
  });

  it("teaches that the player placing the final enclosing wall wins", () => {
    const lesson = createTutorialLessons()[6];
    const preview = previewMove(lesson.initialState, lesson.target);
    const result = completeTutorialMove(
      lesson,
      lesson.initialState,
      lesson.target,
      preview,
    );

    expect(lesson.initialState.size).toBe(17);
    expect(preview?.wouldTrap).toBe(true);
    expect(result?.state.outcome).toEqual({
      status: "won",
      winner: "white",
      reason: "trapped",
    });
  });
});
