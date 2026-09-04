export type Player = "white" | "black";

export interface Outcome {
  status: "playing" | "won" | "draw";
  winner: Player | null;
  reason: string | null;
  exit_direction: string | null;
}

export interface Wall {
  orientation: "horizontal" | "vertical";
  row: number;
  col: number;
  color: Player;
}

export interface BoardState {
  size: number;
  posts: string;
  ball: { row: number; col: number };
  turn: Player;
  outcome: Outcome;
  walls: Wall[];
}

export interface Candidate {
  action: number;
  prior: number;
  visits: number;
  q: number;
}

export interface MoveFeatures {
  legal_actions: number;
  first_step_costs: number[];
  directional_exit_distances: number[];
  unique_gradient: boolean;
  gradient_delta: number | null;
  white_posts: number;
  black_posts: number;
  white_floating: number;
  black_floating: number;
  white_anchored: number;
  black_anchored: number;
  white_walls: number;
  black_walls: number;
  new_walls: number;
  ball_moved: boolean;
  ball_move_direction: string | null;
  reply_resistance: number | null;
}

export interface ResearchMove {
  ply: number;
  turn: Player;
  action: number;
  move_kind: string;
  root_value: number;
  policy_entropy: number;
  state_hash: string;
  state: BoardState;
  features: MoveFeatures;
  candidates: Candidate[];
}

export interface GameSummary {
  game_id: string;
  white_model_id: string;
  black_model_id: string;
  board_size: number;
  search_simulations: number;
  winner: Player | null;
  reason: string;
  plies: number;
  first_ball_move: number | null;
}

export interface ResearchGame extends Omit<GameSummary, "plies" | "first_ball_move"> {
  moves: ResearchMove[];
  final_state: BoardState;
}
