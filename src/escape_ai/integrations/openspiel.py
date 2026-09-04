"""OpenSpiel adapter backed exclusively by the optimized Escape rules state."""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import pyspiel  # type: ignore[import-not-found]

from escape_ai import _escape_core

WHITE_PLAYER = 0
BLACK_PLAYER = 1
DEFAULT_SIZE = 17

GAME_TYPE = pyspiel.GameType(
    short_name="python_escape_ai",
    long_name="Escape AI",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.ZERO_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=2,
    min_num_players=2,
    provides_information_state_string=False,
    provides_information_state_tensor=False,
    provides_observation_string=False,
    provides_observation_tensor=False,
    parameter_specification={"size": DEFAULT_SIZE},
)


def _validated_size(params: Mapping[str, Any]) -> int:
    size = int(params.get("size", DEFAULT_SIZE))
    if size < 3 or size > 17 or size % 2 == 0:
        raise ValueError("Escape board size must be odd and between 3 and 17")
    return size


class EscapeSpielGame(pyspiel.Game):  # type: ignore[misc]
    """An OpenSpiel game whose transitions call the canonical C++ core."""

    def __init__(self, params: Mapping[str, Any] | None = None) -> None:
        parameters = dict(params or {})
        size = _validated_size(parameters)
        parameters["size"] = size
        game_info = pyspiel.GameInfo(
            num_distinct_actions=(size + 1) ** 2,
            max_chance_outcomes=0,
            num_players=2,
            min_utility=-1.0,
            max_utility=1.0,
            utility_sum=0.0,
            max_game_length=2 * (size + 1) ** 2,
        )
        super().__init__(GAME_TYPE, game_info, parameters)
        self.size = size

    def new_initial_state(self) -> EscapeSpielState:
        return EscapeSpielState(self)


class EscapeSpielState(pyspiel.State):  # type: ignore[misc]
    """OpenSpiel state wrapper around one immutable optimized state snapshot."""

    def __init__(
        self,
        game: EscapeSpielGame,
        core_state: _escape_core.State | None = None,
    ) -> None:
        super().__init__(game)
        self.core_state = core_state or _escape_core.State(game.size)

    def current_player(self) -> int:
        if self.is_terminal():
            return int(pyspiel.PlayerId.TERMINAL)
        return WHITE_PLAYER if self.core_state.turn == "white" else BLACK_PLAYER

    def _legal_actions(self, player: int) -> list[int]:
        if self.is_terminal() or player != self.current_player():
            return []
        return self.core_state.legal_actions()

    def _apply_action(self, action: int) -> None:
        self.core_state = self.core_state.apply(action)

    def _action_to_string(self, player: int, action: int) -> str:
        width = self.core_state.size + 1
        row, col = divmod(action, width)
        player_name = "white" if player == WHITE_PLAYER else "black"
        kind = self.core_state.legal_move_kind(action) or "post"
        return f"{player_name}:{kind}({row},{col})"

    def is_terminal(self) -> bool:
        return self.core_state.outcome["status"] != "playing"

    def returns(self) -> list[float]:
        winner = self.core_state.outcome["winner"]
        if winner is None:
            return [0.0, 0.0]
        return [1.0, -1.0] if winner == "white" else [-1.0, 1.0]

    def __str__(self) -> str:
        width = self.core_state.size + 1
        codes = {None: ".", "white": "W", "black": "B"}
        rows = [
            "".join(codes[self.core_state.post(row, col)] for col in range(width))
            for row in range(width)
        ]
        ball_row, ball_col = self.core_state.ball
        status = self.core_state.outcome["status"]
        header = (
            f"turn={self.core_state.turn} ball=({ball_row},{ball_col}) "
            f"ply={self.core_state.ply} status={status}"
        )
        return "\n".join((header, *rows))


pyspiel.register_game(GAME_TYPE, EscapeSpielGame)


def load_game(size: int = DEFAULT_SIZE) -> EscapeSpielGame:
    """Load the registered adapter through OpenSpiel's public registry."""

    return cast(EscapeSpielGame, pyspiel.load_game(f"python_escape_ai(size={size})"))


@dataclass(frozen=True, slots=True)
class OpenSpielValidationSummary:
    seed: int
    sizes: tuple[int, ...]
    games: int
    states: int
    plies: int


def validate_adapter(
    *,
    games_per_size: int = 20,
    sizes: tuple[int, ...] = (3, 5, 9, 17),
    seed: int = 20260904,
) -> OpenSpielValidationSummary:
    """Run OpenSpiel API checks and deterministic transition comparisons."""

    rng = random.Random(seed)
    states = 0
    plies = 0
    for size in sizes:
        game = load_game(size)
        pyspiel.random_sim_test(
            game,
            num_sims=games_per_size,
            serialize=False,
            verbose=False,
        )
        for _ in range(games_per_size):
            spiel_state = game.new_initial_state()
            core_state = _escape_core.State(size)
            states += 1
            while not spiel_state.is_terminal():
                if spiel_state.legal_actions() != core_state.legal_actions():
                    raise AssertionError("OpenSpiel and core legal actions diverged")
                if spiel_state.core_state.serialize() != core_state.serialize():
                    raise AssertionError("OpenSpiel and core states diverged")
                action = rng.choice(core_state.legal_actions())
                spiel_state.apply_action(action)
                core_state = core_state.apply(action)
                states += 1
                plies += 1
            if spiel_state.core_state.serialize() != core_state.serialize():
                raise AssertionError("OpenSpiel and core terminal states diverged")

    return OpenSpielValidationSummary(
        seed=seed,
        sizes=sizes,
        games=games_per_size * len(sizes),
        states=states,
        plies=plies,
    )
