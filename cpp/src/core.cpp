#include "escape_ai/core.hpp"

#include <algorithm>
#include <array>
#include <queue>
#include <stdexcept>
#include <utility>

namespace escape_ai {
namespace {

constexpr std::array<Direction, 4> kDirections = {
    Direction::kUp,
    Direction::kRight,
    Direction::kDown,
    Direction::kLeft,
};
constexpr std::array<Cell, 4> kDeltas = {
    Cell{-1, 0},
    Cell{0, 1},
    Cell{1, 0},
    Cell{0, -1},
};

std::size_t DirectionIndex(Direction direction) {
  return static_cast<std::size_t>(direction);
}

std::uint64_t SplitMix64(std::uint64_t value) {
  value += 0x9e3779b97f4a7c15ULL;
  value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
  value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
  return value ^ (value >> 31U);
}

void AppendByte(std::string& output, std::uint8_t value) {
  output.push_back(static_cast<char>(value));
}

std::uint8_t ReadByte(const std::string& input, std::size_t index) {
  return static_cast<std::uint8_t>(static_cast<unsigned char>(input.at(index)));
}

bool SwapsAxes(Symmetry symmetry) {
  return symmetry == Symmetry::kRotate90 || symmetry == Symmetry::kRotate270 ||
         symmetry == Symmetry::kDiagonalMain || symmetry == Symmetry::kDiagonalAnti;
}

}  // namespace

Player OtherPlayer(Player player) {
  if (player == Player::kWhite) {
    return Player::kBlack;
  }
  if (player == Player::kBlack) {
    return Player::kWhite;
  }
  throw std::invalid_argument("none is not an active player");
}

Player WinnerForExit(Direction direction) {
  return direction == Direction::kLeft || direction == Direction::kRight
             ? Player::kWhite
             : Player::kBlack;
}

State::State(int size) : size_(size), ball_{size / 2, size / 2} {
  if (size < 3 || size > 17 || size % 2 == 0) {
    throw std::invalid_argument("board size must be an odd integer from 3 through 17");
  }
  posts_.assign(static_cast<std::size_t>((size + 1) * (size + 1)), Player::kNone);
}

int State::VertexIndex(int row, int col) const { return row * (size_ + 1) + col; }

bool State::VertexInside(int row, int col) const {
  return row >= 0 && row <= size_ && col >= 0 && col <= size_;
}

bool State::CellInside(int row, int col) const {
  return row >= 0 && row < size_ && col >= 0 && col < size_;
}

Player State::Post(int row, int col) const {
  if (!VertexInside(row, col)) {
    return Player::kNone;
  }
  return posts_.at(static_cast<std::size_t>(VertexIndex(row, col)));
}

void State::SetPost(int row, int col, Player post) {
  if (!VertexInside(row, col)) {
    throw std::out_of_range("vertex outside board");
  }
  posts_.at(static_cast<std::size_t>(VertexIndex(row, col))) = post;
}

void State::SetBall(Cell ball) {
  if (!CellInside(ball.row, ball.col)) {
    throw std::out_of_range("ball cell outside board");
  }
  ball_ = ball;
}

void State::SetTurn(Player turn) {
  if (turn == Player::kNone) {
    throw std::invalid_argument("none is not an active player");
  }
  turn_ = turn;
}

bool State::HasSameColorNeighbor(int row, int col, Player color) const {
  for (const Cell delta : kDeltas) {
    if (Post(row + delta.row, col + delta.col) == color) {
      return true;
    }
  }
  return false;
}

bool State::IsAnchored(int row, int col) const {
  const Player color = Post(row, col);
  return color != Player::kNone && HasSameColorNeighbor(row, col, color);
}

std::optional<LegalMove> State::GetLegalMove(int action) const {
  if (outcome_.status != OutcomeStatus::kPlaying || action < 0 ||
      action >= static_cast<int>(posts_.size())) {
    return std::nullopt;
  }
  const int row = action / (size_ + 1);
  const int col = action % (size_ + 1);
  const Player occupant = posts_.at(static_cast<std::size_t>(action));
  if (occupant == Player::kNone) {
    return LegalMove{action, row, col, MoveKind::kPlace};
  }
  if (occupant == OtherPlayer(turn_) && !IsAnchored(row, col) &&
      HasSameColorNeighbor(row, col, turn_)) {
    return LegalMove{action, row, col, MoveKind::kReplace};
  }
  return std::nullopt;
}

std::vector<int> State::LegalActions() const {
  std::vector<int> result;
  result.reserve(posts_.size());
  for (int action = 0; action < static_cast<int>(posts_.size()); ++action) {
    if (GetLegalMove(action).has_value()) {
      result.push_back(action);
    }
  }
  return result;
}

std::vector<WallSegment> State::Walls() const {
  std::vector<WallSegment> walls;
  for (int row = 0; row <= size_; ++row) {
    for (int col = 0; col <= size_; ++col) {
      const Player color = Post(row, col);
      if (color == Player::kNone) {
        continue;
      }
      if (col < size_ && Post(row, col + 1) == color) {
        walls.push_back(WallSegment{true, row, col, color});
      }
      if (row < size_ && Post(row + 1, col) == color) {
        walls.push_back(WallSegment{false, row, col, color});
      }
    }
  }
  return walls;
}

bool State::HasHorizontalWall(int row, int col) const {
  const Player left = Post(row, col);
  return left != Player::kNone && Post(row, col + 1) == left;
}

bool State::HasVerticalWall(int row, int col) const {
  const Player top = Post(row, col);
  return top != Player::kNone && Post(row + 1, col) == top;
}

bool State::IsPassageBlocked(Cell cell, Direction direction) const {
  switch (direction) {
    case Direction::kUp:
      return HasHorizontalWall(cell.row, cell.col);
    case Direction::kRight:
      return HasVerticalWall(cell.row, cell.col + 1);
    case Direction::kDown:
      return HasHorizontalWall(cell.row + 1, cell.col);
    case Direction::kLeft:
      return HasVerticalWall(cell.row, cell.col);
  }
  throw std::invalid_argument("unknown direction");
}

std::optional<WalkResult> State::Walk(Cell cell, Direction direction) const {
  if (!CellInside(cell.row, cell.col)) {
    throw std::out_of_range("cell outside board");
  }
  if (IsPassageBlocked(cell, direction)) {
    return std::nullopt;
  }
  const Cell delta = kDeltas.at(DirectionIndex(direction));
  const Cell next{cell.row + delta.row, cell.col + delta.col};
  if (CellInside(next.row, next.col)) {
    return WalkResult{next, std::nullopt};
  }
  return WalkResult{std::nullopt, direction};
}

std::vector<int> State::NearestExitDistances() const {
  std::vector<int> distances(static_cast<std::size_t>(size_ * size_), kInfinity);
  std::queue<Cell> queue;
  for (int row = 0; row < size_; ++row) {
    for (int col = 0; col < size_; ++col) {
      const Cell cell{row, col};
      bool can_exit = false;
      for (const Direction direction : kDirections) {
        const auto step = Walk(cell, direction);
        if (step.has_value() && step->exit_direction.has_value()) {
          can_exit = true;
          break;
        }
      }
      if (can_exit) {
        distances.at(static_cast<std::size_t>(row * size_ + col)) = 1;
        queue.push(cell);
      }
    }
  }

  while (!queue.empty()) {
    const Cell current = queue.front();
    queue.pop();
    const int current_distance =
        distances.at(static_cast<std::size_t>(current.row * size_ + current.col));
    for (const Direction direction : kDirections) {
      const auto step = Walk(current, direction);
      if (!step.has_value() || !step->cell.has_value()) {
        continue;
      }
      const Cell next = *step->cell;
      const std::size_t index = static_cast<std::size_t>(next.row * size_ + next.col);
      if (distances.at(index) <= current_distance + 1) {
        continue;
      }
      distances.at(index) = current_distance + 1;
      queue.push(next);
    }
  }
  return distances;
}

std::array<int, 4> State::FirstStepCosts() const {
  const std::vector<int> distances = NearestExitDistances();
  std::array<int, 4> costs = {kInfinity, kInfinity, kInfinity, kInfinity};
  for (const Direction direction : kDirections) {
    const auto step = Walk(ball_, direction);
    if (!step.has_value()) {
      continue;
    }
    if (step->exit_direction.has_value()) {
      costs.at(DirectionIndex(direction)) = 1;
      continue;
    }
    const Cell next = *step->cell;
    const int remaining =
        distances.at(static_cast<std::size_t>(next.row * size_ + next.col));
    costs.at(DirectionIndex(direction)) =
        remaining >= kInfinity ? kInfinity : remaining + 1;
  }
  return costs;
}

ShortestEscapeInfo State::ShortestEscape() const {
  const std::array<int, 4> costs = FirstStepCosts();
  const int shortest = *std::min_element(costs.begin(), costs.end());
  ShortestEscapeInfo result;
  result.distance = shortest;
  if (shortest >= kInfinity) {
    return result;
  }
  for (const Direction direction : kDirections) {
    if (costs.at(DirectionIndex(direction)) == shortest) {
      result.first_steps.push_back(direction);
    }
  }
  return result;
}

std::array<int, 4> State::DirectionalExitDistances() const {
  std::array<int, 4> exits = {kInfinity, kInfinity, kInfinity, kInfinity};
  std::vector<int> distances(static_cast<std::size_t>(size_ * size_), kInfinity);
  std::queue<Cell> queue;
  distances.at(static_cast<std::size_t>(ball_.row * size_ + ball_.col)) = 0;
  queue.push(ball_);

  while (!queue.empty()) {
    const Cell current = queue.front();
    queue.pop();
    const int current_distance =
        distances.at(static_cast<std::size_t>(current.row * size_ + current.col));
    for (const Direction direction : kDirections) {
      const auto step = Walk(current, direction);
      if (!step.has_value()) {
        continue;
      }
      if (step->exit_direction.has_value()) {
        int& exit_distance = exits.at(DirectionIndex(direction));
        exit_distance = std::min(exit_distance, current_distance + 1);
        continue;
      }
      const Cell next = *step->cell;
      const std::size_t index = static_cast<std::size_t>(next.row * size_ + next.col);
      if (distances.at(index) != kInfinity) {
        continue;
      }
      distances.at(index) = current_distance + 1;
      queue.push(next);
    }
  }
  return exits;
}

State State::Apply(int action) const {
  State result = *this;
  static_cast<void>(result.ApplyInPlace(action));
  return result;
}

UndoToken State::ApplyInPlace(int action) {
  const auto move = GetLegalMove(action);
  if (!move.has_value()) {
    throw std::invalid_argument("illegal action");
  }
  UndoToken token{action, posts_.at(static_cast<std::size_t>(action)), ball_, turn_, ply_, outcome_};
  posts_.at(static_cast<std::size_t>(action)) = turn_;
  const ShortestEscapeInfo shortest = ShortestEscape();
  outcome_ = Outcome{};

  if (shortest.distance >= kInfinity) {
    outcome_ = Outcome{OutcomeStatus::kWon, turn_, WinReason::kTrapped, std::nullopt};
  } else if (shortest.first_steps.size() == 1U) {
    const Direction direction = shortest.first_steps.front();
    const auto step = Walk(ball_, direction);
    if (!step.has_value()) {
      throw std::logic_error("shortest first step cannot be blocked");
    }
    if (step->exit_direction.has_value()) {
      outcome_ = Outcome{
          OutcomeStatus::kWon,
          WinnerForExit(direction),
          WinReason::kEscaped,
          direction,
      };
    } else {
      ball_ = *step->cell;
    }
  }

  ++ply_;
  if (outcome_.status == OutcomeStatus::kPlaying) {
    turn_ = OtherPlayer(turn_);
    AdjudicateTurnStart();
  }
  return token;
}

void State::Undo(const UndoToken& token) {
  if (token.action < 0 || token.action >= static_cast<int>(posts_.size())) {
    throw std::invalid_argument("invalid undo token");
  }
  posts_.at(static_cast<std::size_t>(token.action)) = token.previous_post;
  ball_ = token.ball;
  turn_ = token.turn;
  ply_ = token.ply;
  outcome_ = token.outcome;
}

void State::AdjudicateTurnStart() {
  if (outcome_.status == OutcomeStatus::kPlaying && LegalActions().empty()) {
    outcome_ = Outcome{
        OutcomeStatus::kDraw,
        Player::kNone,
        WinReason::kNoLegalMoves,
        std::nullopt,
    };
  }
}

std::uint64_t State::Hash() const {
  std::uint64_t hash = SplitMix64(0x455343415045ULL ^ static_cast<std::uint64_t>(size_));
  for (std::size_t index = 0; index < posts_.size(); ++index) {
    const Player post = posts_.at(index);
    if (post != Player::kNone) {
      hash ^= SplitMix64(0x100000ULL + index * 3ULL + static_cast<std::uint8_t>(post));
    }
  }
  hash ^= SplitMix64(0x200000ULL + static_cast<std::uint64_t>(ball_.row * size_ + ball_.col));
  hash ^= SplitMix64(0x300000ULL + static_cast<std::uint8_t>(turn_));
  hash ^= SplitMix64(0x400000ULL + static_cast<std::uint8_t>(outcome_.status) * 32ULL +
                     static_cast<std::uint8_t>(outcome_.winner) * 8ULL +
                     static_cast<std::uint8_t>(outcome_.reason));
  if (outcome_.exit_direction.has_value()) {
    hash ^= SplitMix64(0x500000ULL + static_cast<std::uint8_t>(*outcome_.exit_direction));
  }
  return hash;
}

std::string State::Serialize() const {
  std::string output = "EAI1";
  output.reserve(14U + posts_.size());
  AppendByte(output, static_cast<std::uint8_t>(size_));
  AppendByte(output, static_cast<std::uint8_t>(turn_));
  AppendByte(output, static_cast<std::uint8_t>(ball_.row));
  AppendByte(output, static_cast<std::uint8_t>(ball_.col));
  AppendByte(output, static_cast<std::uint8_t>(ply_ & 0xff));
  AppendByte(output, static_cast<std::uint8_t>((ply_ >> 8) & 0xff));
  AppendByte(output, static_cast<std::uint8_t>(outcome_.status));
  AppendByte(output, static_cast<std::uint8_t>(outcome_.winner));
  AppendByte(output, static_cast<std::uint8_t>(outcome_.reason));
  AppendByte(
      output,
      outcome_.exit_direction.has_value()
          ? static_cast<std::uint8_t>(*outcome_.exit_direction)
          : static_cast<std::uint8_t>(0xff));
  for (const Player post : posts_) {
    AppendByte(output, static_cast<std::uint8_t>(post));
  }
  return output;
}

State State::Deserialize(const std::string& data) {
  if (data.size() < 14U || data.substr(0, 4) != "EAI1") {
    throw std::invalid_argument("invalid serialized state header");
  }
  const int size = ReadByte(data, 4);
  State state(size);
  if (data.size() != 14U + state.posts_.size()) {
    throw std::invalid_argument("serialized state length does not match board size");
  }
  state.turn_ = static_cast<Player>(ReadByte(data, 5));
  state.ball_ = Cell{ReadByte(data, 6), ReadByte(data, 7)};
  state.ply_ = ReadByte(data, 8) | (static_cast<int>(ReadByte(data, 9)) << 8);
  state.outcome_.status = static_cast<OutcomeStatus>(ReadByte(data, 10));
  state.outcome_.winner = static_cast<Player>(ReadByte(data, 11));
  state.outcome_.reason = static_cast<WinReason>(ReadByte(data, 12));
  const std::uint8_t exit = ReadByte(data, 13);
  if (ReadByte(data, 10) > static_cast<std::uint8_t>(OutcomeStatus::kDraw) ||
      ReadByte(data, 11) > static_cast<std::uint8_t>(Player::kBlack) ||
      ReadByte(data, 12) > static_cast<std::uint8_t>(WinReason::kNoLegalMoves) ||
      (exit != 0xff && exit > static_cast<std::uint8_t>(Direction::kLeft))) {
    throw std::invalid_argument("invalid enum code in serialized state");
  }
  state.outcome_.exit_direction =
      exit == 0xff ? std::nullopt : std::optional(static_cast<Direction>(exit));
  for (std::size_t index = 0; index < state.posts_.size(); ++index) {
    const Player post = static_cast<Player>(ReadByte(data, 14U + index));
    if (post != Player::kNone && post != Player::kWhite && post != Player::kBlack) {
      throw std::invalid_argument("invalid post code in serialized state");
    }
    state.posts_.at(index) = post;
  }
  const bool valid_playing = state.outcome_.status == OutcomeStatus::kPlaying &&
                             state.outcome_.winner == Player::kNone &&
                             state.outcome_.reason == WinReason::kNone &&
                             !state.outcome_.exit_direction.has_value();
  const bool valid_draw = state.outcome_.status == OutcomeStatus::kDraw &&
                          state.outcome_.winner == Player::kNone &&
                          state.outcome_.reason == WinReason::kNoLegalMoves &&
                          !state.outcome_.exit_direction.has_value();
  const bool valid_escape = state.outcome_.status == OutcomeStatus::kWon &&
                            state.outcome_.winner != Player::kNone &&
                            state.outcome_.reason == WinReason::kEscaped &&
                            state.outcome_.exit_direction.has_value();
  const bool valid_trap = state.outcome_.status == OutcomeStatus::kWon &&
                          state.outcome_.winner != Player::kNone &&
                          state.outcome_.reason == WinReason::kTrapped &&
                          !state.outcome_.exit_direction.has_value();
  if (state.turn_ == Player::kNone || !state.CellInside(state.ball_.row, state.ball_.col) ||
      state.ply_ < 0 || state.ply_ > 2 * (size + 1) * (size + 1)) {
    throw std::invalid_argument("invalid serialized state fields");
  }
  if (!valid_playing && !valid_draw && !valid_escape && !valid_trap) {
    throw std::invalid_argument("inconsistent outcome in serialized state");
  }
  return state;
}

Cell TransformCell(Cell cell, int extent, Symmetry symmetry) {
  const int last = extent - 1;
  switch (symmetry) {
    case Symmetry::kIdentity:
      return cell;
    case Symmetry::kRotate90:
      return Cell{cell.col, last - cell.row};
    case Symmetry::kRotate180:
      return Cell{last - cell.row, last - cell.col};
    case Symmetry::kRotate270:
      return Cell{last - cell.col, cell.row};
    case Symmetry::kFlipHorizontal:
      return Cell{last - cell.row, cell.col};
    case Symmetry::kFlipVertical:
      return Cell{cell.row, last - cell.col};
    case Symmetry::kDiagonalMain:
      return Cell{cell.col, cell.row};
    case Symmetry::kDiagonalAnti:
      return Cell{last - cell.col, last - cell.row};
  }
  throw std::invalid_argument("unknown symmetry");
}

Direction TransformDirection(Direction direction, Symmetry symmetry) {
  constexpr std::array<std::array<Direction, 4>, 8> transforms = {{
      {Direction::kUp, Direction::kRight, Direction::kDown, Direction::kLeft},
      {Direction::kRight, Direction::kDown, Direction::kLeft, Direction::kUp},
      {Direction::kDown, Direction::kLeft, Direction::kUp, Direction::kRight},
      {Direction::kLeft, Direction::kUp, Direction::kRight, Direction::kDown},
      {Direction::kDown, Direction::kRight, Direction::kUp, Direction::kLeft},
      {Direction::kUp, Direction::kLeft, Direction::kDown, Direction::kRight},
      {Direction::kLeft, Direction::kDown, Direction::kRight, Direction::kUp},
      {Direction::kRight, Direction::kUp, Direction::kLeft, Direction::kDown},
  }};
  return transforms.at(static_cast<std::size_t>(symmetry)).at(DirectionIndex(direction));
}

Player TransformPlayer(Player player, Symmetry symmetry) {
  if (player == Player::kNone || !SwapsAxes(symmetry)) {
    return player;
  }
  return OtherPlayer(player);
}

int TransformAction(int action, int size, Symmetry symmetry) {
  const int action_count = (size + 1) * (size + 1);
  if (action < 0 || action >= action_count) {
    throw std::out_of_range("action outside board");
  }
  const Cell transformed =
      TransformCell(Cell{action / (size + 1), action % (size + 1)}, size + 1, symmetry);
  return transformed.row * (size + 1) + transformed.col;
}

State State::Transformed(Symmetry symmetry) const {
  State transformed(size_);
  std::fill(transformed.posts_.begin(), transformed.posts_.end(), Player::kNone);
  for (int row = 0; row <= size_; ++row) {
    for (int col = 0; col <= size_; ++col) {
      const Player post = Post(row, col);
      const Cell target = TransformCell(Cell{row, col}, size_ + 1, symmetry);
      transformed.posts_.at(static_cast<std::size_t>(transformed.VertexIndex(target.row, target.col))) =
          TransformPlayer(post, symmetry);
    }
  }
  transformed.ball_ = TransformCell(ball_, size_, symmetry);
  transformed.turn_ = TransformPlayer(turn_, symmetry);
  transformed.ply_ = ply_;
  transformed.outcome_ = outcome_;
  transformed.outcome_.winner = TransformPlayer(outcome_.winner, symmetry);
  if (outcome_.exit_direction.has_value()) {
    transformed.outcome_.exit_direction = TransformDirection(*outcome_.exit_direction, symmetry);
  }
  return transformed;
}

}  // namespace escape_ai
