import { describe, expect, it } from "vitest";

import { actionName, playerName, signed } from "./format";

describe("viewer formatters", () => {
  it("maps dense actions to board coordinates", () => {
    expect(actionName(0, 17)).toBe("A1");
    expect(actionName(323, 17)).toBe("R18");
  });

  it("renders players and signed values", () => {
    expect(playerName("white")).toBe("白方");
    expect(signed(0.1254)).toBe("+0.125");
    expect(signed(-0.5)).toBe("-0.500");
  });
});
