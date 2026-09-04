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
    parallel_leaves: int = 1


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

    games = play_self_games(
        evaluator,
        config,
        seeds=[seed],
        model_id=model_id,
        game_ids=[game_id_factory() if game_id_factory is not None else uuid.uuid4().hex],
    )
    return games[0]


def play_self_games(
    evaluator: PositionEvaluator,
    config: SelfPlayConfig,
    *,
    seeds: list[int],
    model_id: str,
    game_ids: list[str] | None = None,
) -> list[SelfPlayGame]:
    """Generate a wave of games with one batched network evaluation per simulation."""

    if not seeds:
        return []
    selected_ids = game_ids or [uuid.uuid4().hex for _ in seeds]
    if len(selected_ids) != len(seeds):
        raise ValueError("game_ids and seeds must have equal lengths")
    rngs = [random.Random(seed) for seed in seeds]
    states = [_escape_core.State(config.board_size) for _ in seeds]
    pending: list[list[tuple[bytes, int, str, npt.NDArray[np.float32], float, int]]] = [
        [] for _ in seeds
    ]

    search = PUCTSearch(
        evaluator,
        simulations=config.simulations,
        c_puct=config.c_puct,
        dirichlet_alpha=config.dirichlet_alpha,
        dirichlet_fraction=config.dirichlet_fraction,
        parallel_leaves=config.parallel_leaves,
    )
    active = list(range(len(seeds)))
    while active:
        active_states = [states[index] for index in active]
        active_rngs = [rngs[index] for index in active]
        temperatures = [
            (
                config.temperature
                if state.ply < config.temperature_drop_ply
                else config.late_temperature
            )
            for state in active_states
        ]
        results = search.run_batch(
            active_states,
            active_rngs,
            temperatures=temperatures,
            add_root_noise=True,
            include_statistics=False,
        )
        next_active: list[int] = []
        for index, state, result in zip(active, active_states, results, strict=True):
            pending[index].append(
                (
                    state.serialize(),
                    state.ply,
                    state.turn,
                    result.policy,
                    result.root_value,
                    result.action,
                )
            )
            states[index] = state.apply(result.action)
            if states[index].outcome["status"] == "playing":
                next_active.append(index)
        active = next_active

    games: list[SelfPlayGame] = []
    for index, state in enumerate(states):
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
            for serialized, ply, turn, policy, root_value, action in pending[index]
        )
        games.append(
            SelfPlayGame(
                game_id=selected_ids[index],
                model_id=model_id,
                board_size=config.board_size,
                seed=seeds[index],
                winner=winner,
                reason=str(state.outcome["reason"]),
                positions=positions,
            )
        )
    return games
