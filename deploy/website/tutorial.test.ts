import { describe, expect, it } from "vitest";
import { getPost, getWallSegments, previewMove } from "../src/game";
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

  it("teaches that a right-edge escape awards white even after black moves", () => {
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
