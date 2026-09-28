import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { BoardNeighborDistances } from "../src/components/BoardNeighborDistances";
import { createGame, getNeighborEscapeDistances, setPost } from "../src/game";

describe("full first-direction escape distance hints", () => {
  function render(state: ReturnType<typeof createGame>) {
    return renderToStaticMarkup(createElement(BoardNeighborDistances, {
      ball: state.ball, boardSize: state.size,
      distances: getNeighborEscapeDistances(state), highlightShortest: true,
    }));
  }

  it("includes the first step at the center without highlighting tied routes", () => {
    const html = render(createGame());
    expect(html.match(/>9<\/div>/g)).toHaveLength(4);
    expect(html).toContain("首步向上 9 步");
    expect(html).not.toContain("is-shortest");
  });

  it("shows 1 for an immediate escape, infinity for a wall and the unique minimum", () => {
    const state = { ...setPost(setPost(createGame(), 0, 16, "white"), 0, 17, "white"),
      ball: { row: 0, col: 16 } };
    const html = render(state);
    expect(html).toContain("首步向上 ∞ 步；首步向右 1 步");
    expect(html).toMatch(/is-shortest" data-direction="right"[^>]*>1<\/div>/);
    expect(html).not.toContain(">0</div>");
  });
});
