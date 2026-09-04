"""Batched high-detail neural PUCT game generation."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from escape_ai import _escape_core
from escape_ai.search import PositionEvaluator, PUCTSearch, SearchResult

from .features import PositionFeatures, TransitionFeatures, position_features, transition_features


@dataclass(frozen=True, slots=True)
class ResearchSearchConfig:
    board_size: int = 17
    simulations: int = 512
    c_puct: float = 1.5
    parallel_leaves: int = 16
    temperature: float = 0.0
    opening_temperature: float = 1.0
    opening_plies: int = 0
    add_root_noise: bool = False
    top_candidates: int = 16
    compute_reply_resistance: bool = False


@dataclass(frozen=True, slots=True)
class CandidateStatistics:
    action: int
    prior: float
    visits: int
    mean_value: float


@dataclass(frozen=True, slots=True)
class ResearchMove:
    ply: int
    turn: str
    state: bytes
    state_hash: int
    action: int
    root_value: float
    policy_entropy: float
    features: PositionFeatures
    transition: TransitionFeatures
    candidates: tuple[CandidateStatistics, ...]


@dataclass(frozen=True, slots=True)
class ResearchGame:
    game_id: str
    white_model_id: str
    black_model_id: str
    seed: int
    board_size: int
    search_simulations: int
    winner: str | None
    reason: str
    moves: tuple[ResearchMove, ...]


def _entropy(probabilities: list[float]) -> float:
    return -sum(value * math.log(value) for value in probabilities if value > 0.0)


def play_research_games(
    white_evaluator: PositionEvaluator,
    config: ResearchSearchConfig,
    *,
    seeds: list[int],
    white_model_id: str,
    game_ids: list[str],
    black_evaluator: PositionEvaluator | None = None,
    black_model_id: str | None = None,
) -> list[ResearchGame]:
    if len(seeds) != len(game_ids):
        raise ValueError("research seeds and game IDs must have equal lengths")
    if not seeds:
        return []
    states = [_escape_core.State(config.board_size) for _ in seeds]
    rngs = [random.Random(seed) for seed in seeds]
    moves: list[list[ResearchMove]] = [[] for _ in seeds]
    selected_black_evaluator = black_evaluator or white_evaluator
    selected_black_model_id = black_model_id or white_model_id
    white_search = PUCTSearch(
        white_evaluator,
        simulations=config.simulations,
        c_puct=config.c_puct,
        parallel_leaves=config.parallel_leaves,
    )
    black_search = (
        white_search
        if selected_black_evaluator is white_evaluator
        else PUCTSearch(
            selected_black_evaluator,
            simulations=config.simulations,
            c_puct=config.c_puct,
            parallel_leaves=config.parallel_leaves,
        )
    )
    active = list(range(len(states)))
    while active:
        active_states = [states[index] for index in active]
        opening = active_states[0].ply < config.opening_plies
        temperature = config.opening_temperature if opening else config.temperature
        results_by_index: dict[int, SearchResult] = {}
        groups = (
            [active]
            if white_search is black_search
            else [
                [index for index in active if states[index].turn == "white"],
                [index for index in active if states[index].turn == "black"],
            ]
        )
        for group in groups:
            if not group:
                continue
            search = white_search if states[group[0]].turn == "white" else black_search
            group_results = search.run_batch(
                [states[index] for index in group],
                [rngs[index] for index in group],
                temperatures=[temperature] * len(group),
                add_root_noise=config.add_root_noise and opening,
                include_statistics=True,
            )
            results_by_index.update(zip(group, group_results, strict=True))
        next_active: list[int] = []
        for index, before in zip(active, active_states, strict=True):
            result = results_by_index[index]
            after = before.apply(result.action)
            probabilities = [float(value) for value in result.policy if value > 0.0]
            candidates = tuple(
                CandidateStatistics(item.action, item.prior, item.visits, item.mean_value)
                for item in result.statistics[: config.top_candidates]
            )
            moves[index].append(
                ResearchMove(
                    ply=before.ply,
                    turn=before.turn,
                    state=before.serialize(),
                    state_hash=before.hash(),
                    action=result.action,
                    root_value=result.root_value,
                    policy_entropy=_entropy(probabilities),
                    features=position_features(before),
                    transition=transition_features(
                        before,
                        result.action,
                        after,
                        compute_reply_resistance=config.compute_reply_resistance,
                    ),
                    candidates=candidates,
                )
            )
            states[index] = after
            if after.outcome["status"] == "playing":
                next_active.append(index)
        active = next_active

    return [
        ResearchGame(
            game_id=game_ids[index],
            white_model_id=white_model_id,
            black_model_id=selected_black_model_id,
            seed=seed,
            board_size=config.board_size,
            search_simulations=config.simulations,
            winner=states[index].outcome["winner"],
            reason=str(states[index].outcome["reason"]),
            moves=tuple(moves[index]),
        )
        for index, seed in enumerate(seeds)
    ]
