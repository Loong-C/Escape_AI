#include "escape_ai/core.hpp"

#include <cassert>
#include <iostream>

using escape_ai::Cell;
using escape_ai::Direction;
using escape_ai::MoveKind;
using escape_ai::OutcomeStatus;
using escape_ai::Player;
using escape_ai::State;
using escape_ai::Symmetry;
using escape_ai::WinReason;

int main() {
  State standard;
  assert(standard.size() == 17);
  assert(standard.ball() == Cell(8, 8));
  assert(standard.posts().size() == 324U);
  const std::array<int, 4> expected_costs = {9, 9, 9, 9};
  assert(standard.FirstStepCosts() == expected_costs);

  State replacement(3);
  replacement.SetPost(2, 2, Player::kBlack);
  replacement.SetPost(2, 1, Player::kWhite);
  const int replacement_action = replacement.VertexIndex(2, 2);
  const auto legal = replacement.GetLegalMove(replacement_action);
  assert(legal.has_value());
  assert(legal->kind == MoveKind::kReplace);
  const State replaced = replacement.Apply(replacement_action);
  assert(replaced.Post(2, 2) == Player::kWhite);

  State trapped(3);
  trapped.SetPost(1, 1, Player::kWhite);
  trapped.SetPost(1, 2, Player::kWhite);
  trapped.SetPost(2, 1, Player::kWhite);
  const State terminal = trapped.Apply(trapped.VertexIndex(2, 2));
  assert(terminal.outcome().status == OutcomeStatus::kWon);
  assert(terminal.outcome().winner == Player::kWhite);
  assert(terminal.outcome().reason == WinReason::kTrapped);

  State exiting(3);
  exiting.SetBall(Cell{1, 2});
  exiting.SetTurn(Player::kBlack);
  const State escaped = exiting.Apply(0);
  assert(escaped.outcome().status == OutcomeStatus::kWon);
  assert(escaped.outcome().winner == Player::kWhite);
  assert(escaped.outcome().exit_direction == Direction::kRight);

  const std::string serialized = terminal.Serialize();
  const State restored = State::Deserialize(serialized);
  assert(restored.Hash() == terminal.Hash());
  assert(restored.posts() == terminal.posts());
  assert(restored.outcome() == terminal.outcome());

  std::string invalid = serialized;
  invalid.at(10) = static_cast<char>(OutcomeStatus::kPlaying);
  bool rejected_invalid_outcome = false;
  try {
    static_cast<void>(State::Deserialize(invalid));
  } catch (const std::invalid_argument&) {
    rejected_invalid_outcome = true;
  }
  assert(rejected_invalid_outcome);

  State undo_state(5);
  const std::uint64_t before_hash = undo_state.Hash();
  const auto token = undo_state.ApplyInPlace(0);
  undo_state.Undo(token);
  assert(undo_state.Hash() == before_hash);

  const State rotated = replacement.Transformed(Symmetry::kRotate90);
  const int rotated_action =
      escape_ai::TransformAction(replacement_action, replacement.size(), Symmetry::kRotate90);
  assert(rotated.GetLegalMove(rotated_action).has_value());

  std::cout << "escape_core_tests: ok\n";
  return 0;
}
