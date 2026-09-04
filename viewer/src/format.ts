import type { Outcome, Player } from "./types";

export function playerName(player: Player | null): string {
  if (player === "white") return "白方";
  if (player === "black") return "黑方";
  return "和棋";
}

export function actionName(action: number, boardSize: number): string {
  const width = boardSize + 1;
  const row = Math.floor(action / width);
  const col = action % width;
  return `${String.fromCharCode(65 + col)}${row + 1}`;
}

export function outcomeText(outcome: Outcome): string {
  if (outcome.status === "playing") return `${playerName(outcome.winner)}进行中`;
  if (outcome.status === "draw") return "和棋";
  return `${playerName(outcome.winner)}胜 · ${outcome.reason === "escaped" ? "成功逃脱" : "困住对手"}`;
}

export function signed(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(3)}`;
}
