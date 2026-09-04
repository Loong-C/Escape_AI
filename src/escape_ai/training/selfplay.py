"""Deterministic AlphaZero self-play game generation."""

from __future__ import annotations

import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from escape_ai import _escape_core
from escape_ai.search.puct import PositionEvaluator, PUCTSearch


@dataclass(frozen=True, slots=True)
class SelfPlayConfig:
    board_size: int = 17
    simulations: int = 200
    c_puct: float = 1.5
    dirichlet_alpha: float = 0.15
    dirichlet_fraction: float = 0.25
    temperature: float = 1.0
    temperature_drop_ply: int = 40
    late_temperature: float = 0.1


@dataclass(frozen=True, slots=True)
class SelfPlayPosition:
    state: bytes
    ply: int
    turn: str
    policy: npt.NDArray[np.float32]
    root_value: float
    action: int
    value_target: float


@dataclass(frozen=True, slots=True)
class SelfPlayGame:
    game_id: str
    model_id: str
    board_size: int
    seed: int
    winner: str | None
    reason: str
    positions: tuple[SelfPlayPosition, ...]

    @property
    def plies(self) -> int:
        return len(self.positions)


def play_self_game(
    evaluator: PositionEvaluator,
    config: SelfPlayConfig,
    *,
    seed: int,
    model_id: str,
    game_id_factory: Callable[[], str] | None = None,
) -> SelfPlayGame:
    """Generate one no-resignation game and label it from each side-to-move."""

    rng = random.Random(seed)
    state = _escape_core.State(config.board_size)
    search = PUCTSearch(
        evaluator,
        simulations=config.simulations,
        c_puct=config.c_puct,
        dirichlet_alpha=config.dirichlet_alpha,
        dirichlet_fraction=config.dirichlet_fraction,
    )
    pending: list[tuple[bytes, int, str, npt.NDArray[np.float32], float, int]] = []
    while state.outcome["status"] == "playing":
        temperature = (
            config.temperature
            if state.ply < config.temperature_drop_ply
            else config.late_temperature
        )
        result = search.run(
            state,
            rng,
            temperature=temperature,
            add_root_noise=True,
        )
        pending.append(
            (
                state.serialize(),
                state.ply,
                state.turn,
                result.policy,
                result.root_value,
                result.action,
            )
        )
        state = state.apply(result.action)

    winner = state.outcome["winner"]
    positions = tuple(
        SelfPlayPosition(
            state=serialized,
            ply=ply,
            turn=turn,
            policy=policy,
            root_value=root_value,
            action=action,
            value_target=(0.0 if winner is None else 1.0 if winner == turn else -1.0),
        )
        for serialized, ply, turn, policy, root_value, action in pending
    )
    make_id = game_id_factory or (lambda: uuid.uuid4().hex)
    return SelfPlayGame(
        game_id=make_id(),
        model_id=model_id,
        board_size=config.board_size,
        seed=seed,
        winner=winner,
        reason=str(state.outcome["reason"]),
        positions=positions,
    )
