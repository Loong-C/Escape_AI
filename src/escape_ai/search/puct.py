"""Policy-guided Monte Carlo tree search with explicit player perspectives."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import numpy.typing as npt
import torch

from escape_ai import _escape_core
from escape_ai.training import PolicyValueNet, encode_state


@dataclass(frozen=True, slots=True)
class Evaluation:
    priors: dict[int, float]
    value: float


class PositionEvaluator(Protocol):
    def evaluate(self, states: Sequence[_escape_core.State]) -> list[Evaluation]: ...


@dataclass(frozen=True, slots=True)
class UniformEvaluator:
    """Zero-value, uniform-policy evaluator for tests and ablations."""

    def evaluate(self, states: Sequence[_escape_core.State]) -> list[Evaluation]:
        results: list[Evaluation] = []
        for state in states:
            actions = state.legal_actions()
            probability = 1.0 / len(actions)
            results.append(Evaluation({action: probability for action in actions}, 0.0))
        return results


class TorchEvaluator:
    """Batched masked inference for a PolicyValueNet."""

    def __init__(self, model: PolicyValueNet, device: torch.device | str) -> None:
        self.model = model.to(device)
        self.device = torch.device(device)
        self.model.eval()

    def evaluate(self, states: Sequence[_escape_core.State]) -> list[Evaluation]:
        if not states:
            return []
        sizes = {state.size for state in states}
        if len(sizes) != 1:
            raise ValueError("a network inference batch must use one board size")
        batch = torch.from_numpy(np.stack([encode_state(state) for state in states])).to(
            self.device
        )
        with torch.inference_mode():
            logits, values = self.model(batch)

        results: list[Evaluation] = []
        for index, state in enumerate(states):
            legal = state.legal_actions()
            legal_indices = torch.tensor(legal, dtype=torch.long, device=self.device)
            probabilities = torch.softmax(logits[index, legal_indices], dim=0).cpu().tolist()
            results.append(
                Evaluation(
                    dict(zip(legal, (float(value) for value in probabilities), strict=True)),
                    float(values[index].item()),
                )
            )
        return results


@dataclass(slots=True)
class SearchEdge:
    prior: float
    visits: int = 0
    value_sum: float = 0.0
    child: SearchNode | None = None

    @property
    def mean_value(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


@dataclass(slots=True)
class SearchNode:
    state: _escape_core.State
    visits: int = 0
    edges: dict[int, SearchEdge] = field(default_factory=dict)
    expanded: bool = False


@dataclass(frozen=True, slots=True)
class ActionStatistics:
    action: int
    prior: float
    visits: int
    mean_value: float


@dataclass(frozen=True, slots=True)
class SearchResult:
    action: int
    policy: npt.NDArray[np.float32]
    root_value: float
    statistics: tuple[ActionStatistics, ...]


class PUCTSearch:
    def __init__(
        self,
        evaluator: PositionEvaluator,
        *,
        simulations: int = 200,
        c_puct: float = 1.5,
        dirichlet_alpha: float = 0.3,
        dirichlet_fraction: float = 0.25,
    ) -> None:
        if simulations < 1:
            raise ValueError("simulations must be positive")
        self.evaluator = evaluator
        self.simulations = simulations
        self.c_puct = c_puct
        self.dirichlet_alpha = dirichlet_alpha
        self.dirichlet_fraction = dirichlet_fraction

    def run(
        self,
        state: _escape_core.State,
        rng: random.Random,
        *,
        temperature: float = 0.0,
        add_root_noise: bool = False,
    ) -> SearchResult:
        if state.outcome["status"] != "playing":
            raise ValueError("cannot search a terminal state")
        root = SearchNode(state)
        self._expand(root)
        if add_root_noise:
            self._add_root_noise(root, rng)

        for _ in range(self.simulations):
            node = root
            path: list[tuple[SearchNode, SearchEdge]] = []
            while node.expanded and node.edges:
                action, edge = self._select(node)
                if edge.child is None:
                    edge.child = SearchNode(node.state.apply(action))
                path.append((node, edge))
                node = edge.child
                if node.state.outcome["status"] != "playing":
                    break

            if node.state.outcome["status"] == "playing":
                value = self._expand(node)
            else:
                winner = node.state.outcome["winner"]
                value = 0.0 if winner is None else (1.0 if winner == node.state.turn else -1.0)
            value_player = node.state.turn
            node.visits += 1
            for parent, edge in reversed(path):
                parent_player = parent.state.turn
                if parent_player != value_player:
                    value = -value
                edge.visits += 1
                edge.value_sum += value
                parent.visits += 1
                value_player = parent_player

        visits = np.zeros((state.size + 1) ** 2, dtype=np.float32)
        statistics: list[ActionStatistics] = []
        for action, edge in root.edges.items():
            visits[action] = edge.visits
            statistics.append(ActionStatistics(action, edge.prior, edge.visits, edge.mean_value))
        policy = self._visit_policy(visits, 1.0)
        selection_policy = self._visit_policy(visits, temperature)
        action = self._sample_action(selection_policy, rng)
        statistics.sort(key=lambda item: (-item.visits, item.action))
        root_value = sum(edge.value_sum for edge in root.edges.values()) / max(root.visits, 1)
        return SearchResult(action, policy, root_value, tuple(statistics))

    def _expand(self, node: SearchNode) -> float:
        evaluation = self.evaluator.evaluate([node.state])[0]
        legal = node.state.legal_actions()
        priors = np.array([max(evaluation.priors.get(action, 0.0), 0.0) for action in legal])
        total = float(priors.sum())
        if not math.isfinite(total) or total <= 0.0:
            priors.fill(1.0 / len(legal))
        else:
            priors /= total
        node.edges = {
            action: SearchEdge(float(prior)) for action, prior in zip(legal, priors, strict=True)
        }
        node.expanded = True
        return evaluation.value

    def _select(self, node: SearchNode) -> tuple[int, SearchEdge]:
        scale = math.sqrt(max(node.visits, 1))

        def score(item: tuple[int, SearchEdge]) -> tuple[float, int]:
            action, edge = item
            exploration = self.c_puct * edge.prior * scale / (1 + edge.visits)
            return edge.mean_value + exploration, -action

        return max(node.edges.items(), key=score)

    def _add_root_noise(self, root: SearchNode, rng: random.Random) -> None:
        edges = list(root.edges.values())
        if not edges or self.dirichlet_fraction <= 0.0:
            return
        noise_rng = np.random.default_rng(rng.getrandbits(64))
        noise = noise_rng.dirichlet(np.full(len(edges), self.dirichlet_alpha))
        keep = 1.0 - self.dirichlet_fraction
        for edge, sample in zip(edges, noise, strict=True):
            edge.prior = keep * edge.prior + self.dirichlet_fraction * float(sample)

    @staticmethod
    def _visit_policy(
        visits: npt.NDArray[np.float32], temperature: float
    ) -> npt.NDArray[np.float32]:
        policy = np.zeros_like(visits)
        if temperature <= 1e-8:
            best = int(np.flatnonzero(visits == visits.max())[0])
            policy[best] = 1.0
            return policy
        weights = np.power(visits.astype(np.float64), 1.0 / temperature)
        total = float(weights.sum())
        if total <= 0.0:
            raise AssertionError("search produced no visited actions")
        return (weights / total).astype(np.float32)

    @staticmethod
    def _sample_action(policy: npt.NDArray[np.float32], rng: random.Random) -> int:
        actions = np.flatnonzero(policy)
        weights = [float(policy[action]) for action in actions]
        return int(rng.choices(actions.tolist(), weights=weights, k=1)[0])
