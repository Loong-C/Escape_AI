#include "escape_ai/core.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <array>
#include <optional>
#include <stdexcept>
#include <string>

namespace py = pybind11;
using escape_ai::Direction;
using escape_ai::MoveKind;
using escape_ai::Outcome;
using escape_ai::Player;
using escape_ai::State;
using escape_ai::Symmetry;
using escape_ai::WinReason;

namespace {

std::string PlayerName(Player player) {
  if (player == Player::kWhite) {
    return "white";
  }
  if (player == Player::kBlack) {
    return "black";
  }
  throw std::invalid_argument("none has no player name");
}

Player ParsePlayer(const std::string& player) {
  if (player == "white") {
    return Player::kWhite;
  }
  if (player == "black") {
    return Player::kBlack;
  }
  throw std::invalid_argument("player must be white or black");
}

std::string DirectionName(Direction direction) {
  constexpr std::array<const char*, 4> names = {"up", "right", "down", "left"};
  return names.at(static_cast<std::size_t>(direction));
}

std::string ReasonName(WinReason reason) {
  switch (reason) {
    case WinReason::kEscaped:
      return "escaped";
    case WinReason::kTrapped:
      return "trapped";
    case WinReason::kNoLegalMoves:
      return "no-legal-moves";
    case WinReason::kNone:
      break;
  }
  throw std::invalid_argument("none has no reason name");
}

py::object OptionalPlayer(Player player) {
  return player == Player::kNone ? py::none() : py::cast(PlayerName(player));
}

py::object OptionalReason(WinReason reason) {
  return reason == WinReason::kNone ? py::none() : py::cast(ReasonName(reason));
}

py::object OptionalDirection(const std::optional<Direction>& direction) {
  return direction.has_value() ? py::cast(DirectionName(*direction)) : py::none();
}

py::dict OutcomeDict(const Outcome& outcome) {
  std::string status = "playing";
  if (outcome.status == escape_ai::OutcomeStatus::kWon) {
    status = "won";
  } else if (outcome.status == escape_ai::OutcomeStatus::kDraw) {
    status = "draw";
  }
  py::dict result;
  result["status"] = status;
  result["winner"] = OptionalPlayer(outcome.winner);
  result["reason"] = OptionalReason(outcome.reason);
  result["exit_direction"] = OptionalDirection(outcome.exit_direction);
  return result;
}

py::list PostsList(const State& state) {
  py::list result;
  for (const Player post : state.posts()) {
    result.append(post == Player::kNone ? py::none() : py::cast(PlayerName(post)));
  }
  return result;
}

py::object PostObject(const State& state, int row, int col) {
  const Player post = state.Post(row, col);
  return post == Player::kNone ? py::none() : py::cast(PlayerName(post));
}

std::string MoveKindName(MoveKind kind) {
  return kind == MoveKind::kPlace ? "place" : "replace";
}

}  // namespace

PYBIND11_MODULE(_escape_core, module) {
  module.doc() = "C++20 optimized rules core for Escape";
  module.attr("INFINITY_DISTANCE") = escape_ai::kInfinity;

  py::enum_<Symmetry>(module, "Symmetry")
      .value("IDENTITY", Symmetry::kIdentity)
      .value("ROTATE_90", Symmetry::kRotate90)
      .value("ROTATE_180", Symmetry::kRotate180)
      .value("ROTATE_270", Symmetry::kRotate270)
      .value("FLIP_HORIZONTAL", Symmetry::kFlipHorizontal)
      .value("FLIP_VERTICAL", Symmetry::kFlipVertical)
      .value("DIAGONAL_MAIN", Symmetry::kDiagonalMain)
      .value("DIAGONAL_ANTI", Symmetry::kDiagonalAnti)
      .export_values();

  py::class_<escape_ai::UndoToken>(module, "UndoToken");

  py::class_<State>(module, "State")
      .def(py::init<int>(), py::arg("size") = 17)
      .def_property_readonly("size", &State::size)
      .def_property_readonly("ply", &State::ply)
      .def_property_readonly("ball", [](const State& state) {
        const auto ball = state.ball();
        return py::make_tuple(ball.row, ball.col);
      })
      .def_property_readonly("turn", [](const State& state) { return PlayerName(state.turn()); })
      .def_property_readonly("posts", &PostsList)
      .def_property_readonly("outcome", [](const State& state) {
        return OutcomeDict(state.outcome());
      })
      .def("post", &PostObject)
      .def("set_post", [](State& state, int row, int col, const py::object& value) {
        state.SetPost(
            row,
            col,
            value.is_none() ? Player::kNone : ParsePlayer(py::cast<std::string>(value)));
      })
      .def("set_ball", [](State& state, int row, int col) {
        state.SetBall(escape_ai::Cell{row, col});
      })
      .def("set_turn", [](State& state, const std::string& player) {
        state.SetTurn(ParsePlayer(player));
      })
      .def("is_anchored", &State::IsAnchored)
      .def("legal_move_kind", [](const State& state, int action) -> py::object {
        const auto move = state.GetLegalMove(action);
        return move.has_value() ? py::cast(MoveKindName(move->kind)) : py::none();
      })
      .def("legal_actions", &State::LegalActions)
      .def("walls", [](const State& state) {
        py::list result;
        for (const auto& wall : state.Walls()) {
          result.append(py::make_tuple(
              wall.horizontal ? "horizontal" : "vertical",
              wall.row,
              wall.col,
              PlayerName(wall.color)));
        }
        return result;
      })
      .def("first_step_costs", &State::FirstStepCosts)
      .def("directional_exit_distances", &State::DirectionalExitDistances)
      .def("shortest_escape", [](const State& state) {
        const auto shortest = state.ShortestEscape();
        py::dict result;
        result["distance"] = shortest.distance;
        py::list directions;
        for (const Direction direction : shortest.first_steps) {
          directions.append(DirectionName(direction));
        }
        result["first_steps"] = directions;
        return result;
      })
      .def("apply", &State::Apply)
      .def("apply_in_place", &State::ApplyInPlace)
      .def("undo", &State::Undo)
      .def("adjudicate_turn_start", &State::AdjudicateTurnStart)
      .def("hash", &State::Hash)
      .def("serialize", [](const State& state) { return py::bytes(state.Serialize()); })
      .def_static("deserialize", [](const py::bytes& data) {
        return State::Deserialize(static_cast<std::string>(data));
      })
      .def("transformed", &State::Transformed);

  module.def("transform_action", &escape_ai::TransformAction);
}

