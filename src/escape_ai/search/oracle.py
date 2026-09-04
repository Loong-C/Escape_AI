"""Exact alpha-beta solver for small boards and bounded endgame subspaces."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum

from escape_ai import _escape_core

from .common import ordered_actions, terminal_value


class SearchLimitExceeded(RuntimeError):
    pass


class Bound(StrEnum):
    EXACT = "exact"
    LOWER = "lower"
    UPPER = "upper"


@dataclass(frozen=True, slots=True)
class _Entry:
    value: int
    bound: Bound
    best_actions: tuple[int, ...]


@dataclass(slots=True)
class _Context:
    deadline: float
    maximum_nodes: int
    nodes: int = 0
    table: dict[bytes, _Entry] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OracleResult:
    value: int
    best_actions: tuple[int, ...]
    nodes: int
    table_entries: int
    elapsed_seconds: float


def solve_exact(
    state: _escape_core.State,
    *,
    time_limit_seconds: float = 60.0,
    maximum_nodes: int = 5_000_000,
) -> OracleResult:
    if state.outcome["status"] != "playing":
        raise ValueError("oracle root must be a playing state")
    started = time.perf_counter()
    context = _Context(started + time_limit_seconds, maximum_nodes)
    # The wider root window enumerates every equally optimal root action. Values
    # are still restricted to {-1, 0, 1}; the internal calls retain alpha-beta
    # pruning as their windows narrow.
    value, actions = _negamax(state, -2, 2, context)
    return OracleResult(
        value=value,
        best_actions=actions,
        nodes=context.nodes,
        table_entries=len(context.table),
        elapsed_seconds=time.perf_counter() - started,
    )


def _negamax(
    state: _escape_core.State,
    alpha: int,
    beta: int,
    context: _Context,
) -> tuple[int, tuple[int, ...]]:
    if context.nodes >= context.maximum_nodes or time.perf_counter() >= context.deadline:
        raise SearchLimitExceeded(
            f"exact search exceeded {context.maximum_nodes} nodes or its time limit"
        )
    context.nodes += 1
    key = state.serialize()
    cached = context.table.get(key)
    if cached is not None:
        if cached.bound is Bound.EXACT:
            return cached.value, cached.best_actions
        if cached.bound is Bound.LOWER:
            alpha = max(alpha, cached.value)
        else:
            beta = min(beta, cached.value)
        if alpha >= beta:
            return cached.value, cached.best_actions

    original_alpha = alpha
    original_beta = beta
    player = state.turn
    best_value = -2
    best_actions: list[int] = []
    for action in ordered_actions(state, player):
        child = state.apply(action)
        terminal = terminal_value(child, player)
        if terminal is None:
            child_value, _ = _negamax(child, -beta, -alpha, context)
            value = -child_value
        else:
            value = int(terminal)
        if value > best_value:
            best_value = value
            best_actions = [action]
        elif value == best_value:
            best_actions.append(action)
        alpha = max(alpha, best_value)
        if alpha >= beta:
            break

    if not best_actions:
        raise AssertionError("playing state had no legal actions")
    bound = Bound.EXACT
    if best_value <= original_alpha:
        bound = Bound.UPPER
    elif best_value >= original_beta:
        bound = Bound.LOWER
    entry = _Entry(best_value, bound, tuple(best_actions))
    context.table[key] = entry
    return entry.value, entry.best_actions
