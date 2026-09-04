"""Fixed non-neural baseline agents."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Protocol

from escape_ai import _escape_core

from .common import heuristic_value, ordered_actions, terminal_value


class Agent(Protocol):
    @property
    def name(self) -> str: ...

    def select_action(self, state: _escape_core.State, rng: random.Random) -> int: ...


@dataclass(frozen=True, slots=True)
class RandomAgent:
    name: str = "random"

    def select_action(self, state: _escape_core.State, rng: random.Random) -> int:
        return rng.choice(state.legal_actions())


@dataclass(frozen=True, slots=True)
class GreedyAgent:
    name: str = "greedy"

    def select_action(self, state: _escape_core.State, rng: random.Random) -> int:
        perspective = state.turn
        scored = [
            (heuristic_value(state.apply(action), perspective), action)
            for action in state.legal_actions()
        ]
        best = max(score for score, _ in scored)
        return rng.choice([action for score, action in scored if score == best])


@dataclass(frozen=True, slots=True)
class HeuristicAgent:
    depth: int = 2
    maximum_branching: int = 64
    name: str = "heuristic"

    def select_action(self, state: _escape_core.State, rng: random.Random) -> int:
        del rng
        perspective = state.turn
        actions = ordered_actions(state, perspective, self.maximum_branching)
        best_action = actions[0]
        best_value = -math.inf
        alpha = -math.inf
        for action in actions:
            value = self._search(
                state.apply(action),
                self.depth - 1,
                perspective,
                alpha,
                math.inf,
            )
            if value > best_value:
                best_value = value
                best_action = action
            alpha = max(alpha, value)
        return best_action

    def _search(
        self,
        state: _escape_core.State,
        depth: int,
        perspective: str,
        alpha: float,
        beta: float,
    ) -> float:
        terminal = terminal_value(state, perspective)
        if terminal is not None:
            return terminal * 1_000_000.0
        if depth <= 0:
            return heuristic_value(state, perspective)

        maximizing = state.turn == perspective
        actions = ordered_actions(state, perspective, self.maximum_branching)
        if maximizing:
            value = -math.inf
            for action in actions:
                value = max(
                    value,
                    self._search(state.apply(action), depth - 1, perspective, alpha, beta),
                )
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value

        value = math.inf
        for action in actions:
            value = min(
                value,
                self._search(state.apply(action), depth - 1, perspective, alpha, beta),
            )
            beta = min(beta, value)
            if alpha >= beta:
                break
        return value


@dataclass(slots=True)
class _MCTSNode:
    state: _escape_core.State
    parent: _MCTSNode | None = None
    action: int | None = None
    children: list[_MCTSNode] = field(default_factory=list)
    unexpanded: list[int] = field(default_factory=list)
    visits: int = 0
    value_sum: float = 0.0

    @classmethod
    def create(
        cls,
        state: _escape_core.State,
        parent: _MCTSNode | None = None,
        action: int | None = None,
    ) -> _MCTSNode:
        return cls(state, parent, action, unexpanded=list(state.legal_actions()))


@dataclass(frozen=True, slots=True)
class PureMCTSAgent:
    simulations: int = 200
    exploration: float = math.sqrt(2.0)
    name: str = "pure-mcts"

    def select_action(self, state: _escape_core.State, rng: random.Random) -> int:
        root_player = state.turn
        legal_actions = state.legal_actions()
        immediate_wins = [
            action
            for action in legal_actions
            if state.apply(action).outcome["winner"] == root_player
        ]
        if immediate_wins:
            return rng.choice(immediate_wins)

        root = _MCTSNode.create(state)
        for _ in range(self.simulations):
            node = root
            while not node.unexpanded and node.children:
                node = self._select_child(node, root_player)
            if node.unexpanded and node.state.outcome["status"] == "playing":
                action_index = rng.randrange(len(node.unexpanded))
                action = node.unexpanded.pop(action_index)
                child = _MCTSNode.create(node.state.apply(action), node, action)
                node.children.append(child)
                node = child
            value = self._rollout(node.state, root_player, rng)
            ancestor: _MCTSNode | None = node
            while ancestor is not None:
                ancestor.visits += 1
                ancestor.value_sum += value
                ancestor = ancestor.parent

        if not root.children:
            raise RuntimeError("MCTS root did not expand")
        maximum_visits = max(child.visits for child in root.children)
        candidates = [child for child in root.children if child.visits == maximum_visits]
        selected = rng.choice(candidates)
        assert selected.action is not None
        return selected.action

    def _select_child(self, node: _MCTSNode, root_player: str) -> _MCTSNode:
        log_parent = math.log(max(node.visits, 1))
        sign = 1.0 if node.state.turn == root_player else -1.0

        def score(child: _MCTSNode) -> float:
            exploit = 0.0 if child.visits == 0 else sign * child.value_sum / child.visits
            explore = self.exploration * math.sqrt(log_parent / max(child.visits, 1))
            return exploit + explore

        return max(node.children, key=score)

    def _rollout(
        self,
        state: _escape_core.State,
        root_player: str,
        rng: random.Random,
    ) -> float:
        current = state
        while current.outcome["status"] == "playing":
            current = current.apply(rng.choice(current.legal_actions()))
        result = terminal_value(current, root_player)
        assert result is not None
        return result
