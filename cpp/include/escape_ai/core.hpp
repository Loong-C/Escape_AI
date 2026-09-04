#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace escape_ai {

constexpr int kInfinity = 1'000'000'000;

enum class Player : std::uint8_t { kNone = 0, kWhite = 1, kBlack = 2 };
enum class Direction : std::uint8_t { kUp = 0, kRight = 1, kDown = 2, kLeft = 3 };
enum class MoveKind : std::uint8_t { kPlace = 0, kReplace = 1 };
enum class OutcomeStatus : std::uint8_t { kPlaying = 0, kWon = 1, kDraw = 2 };
enum class WinReason : std::uint8_t {
  kNone = 0,
  kEscaped = 1,
  kTrapped = 2,
  kNoLegalMoves = 3,
};
enum class Symmetry : std::uint8_t {
  kIdentity = 0,
  kRotate90 = 1,
  kRotate180 = 2,
  kRotate270 = 3,
  kFlipHorizontal = 4,
  kFlipVertical = 5,
  kDiagonalMain = 6,
  kDiagonalAnti = 7,
};

struct Cell {
  int row = 0;
  int col = 0;
  bool operator==(const Cell&) const = default;
};

struct Outcome {
  OutcomeStatus status = OutcomeStatus::kPlaying;
  Player winner = Player::kNone;
  WinReason reason = WinReason::kNone;
  std::optional<Direction> exit_direction;
  bool operator==(const Outcome&) const = default;
};

struct LegalMove {
  int action = 0;
  int row = 0;
  int col = 0;
  MoveKind kind = MoveKind::kPlace;
};

struct WallSegment {
  bool horizontal = true;
  int row = 0;
  int col = 0;
  Player color = Player::kNone;
  bool operator==(const WallSegment&) const = default;
};

struct WalkResult {
  std::optional<Cell> cell;
  std::optional<Direction> exit_direction;
};

struct ShortestEscapeInfo {
  int distance = kInfinity;
  std::vector<Direction> first_steps;
};

struct UndoToken {
  int action = 0;
  Player previous_post = Player::kNone;
  Cell ball;
  Player turn = Player::kWhite;
  int ply = 0;
  Outcome outcome;
};

class State {
 public:
  explicit State(int size = 17);

  [[nodiscard]] int size() const { return size_; }
  [[nodiscard]] int ply() const { return ply_; }
  [[nodiscard]] const std::vector<Player>& posts() const { return posts_; }
  [[nodiscard]] Cell ball() const { return ball_; }
  [[nodiscard]] Player turn() const { return turn_; }
  [[nodiscard]] const Outcome& outcome() const { return outcome_; }

  [[nodiscard]] int VertexIndex(int row, int col) const;
  [[nodiscard]] Player Post(int row, int col) const;
  void SetPost(int row, int col, Player post);
  void SetBall(Cell ball);
  void SetTurn(Player turn);

  [[nodiscard]] bool IsAnchored(int row, int col) const;
  [[nodiscard]] std::optional<LegalMove> GetLegalMove(int action) const;
  [[nodiscard]] std::vector<int> LegalActions() const;
  [[nodiscard]] std::vector<WallSegment> Walls() const;
  [[nodiscard]] bool IsPassageBlocked(Cell cell, Direction direction) const;
  [[nodiscard]] std::optional<WalkResult> Walk(Cell cell, Direction direction) const;
  [[nodiscard]] std::array<int, 4> FirstStepCosts() const;
  [[nodiscard]] std::array<int, 4> DirectionalExitDistances() const;
  [[nodiscard]] ShortestEscapeInfo ShortestEscape() const;

  [[nodiscard]] State Apply(int action) const;
  UndoToken ApplyInPlace(int action);
  void Undo(const UndoToken& token);
  void AdjudicateTurnStart();

  [[nodiscard]] std::uint64_t Hash() const;
  [[nodiscard]] std::string Serialize() const;
  [[nodiscard]] static State Deserialize(const std::string& data);
  [[nodiscard]] State Transformed(Symmetry symmetry) const;

 private:
  int size_ = 17;
  std::vector<Player> posts_;
  Cell ball_;
  Player turn_ = Player::kWhite;
  int ply_ = 0;
  Outcome outcome_;

  [[nodiscard]] bool VertexInside(int row, int col) const;
  [[nodiscard]] bool CellInside(int row, int col) const;
  [[nodiscard]] bool HasSameColorNeighbor(int row, int col, Player color) const;
  [[nodiscard]] bool HasHorizontalWall(int row, int col) const;
  [[nodiscard]] bool HasVerticalWall(int row, int col) const;
  [[nodiscard]] std::vector<int> NearestExitDistances() const;
};

[[nodiscard]] Player OtherPlayer(Player player);
[[nodiscard]] Player WinnerForExit(Direction direction);
[[nodiscard]] Cell TransformCell(Cell cell, int extent, Symmetry symmetry);
[[nodiscard]] Direction TransformDirection(Direction direction, Symmetry symmetry);
[[nodiscard]] Player TransformPlayer(Player player, Symmetry symmetry);
[[nodiscard]] int TransformAction(int action, int size, Symmetry symmetry);

}  // namespace escape_ai

