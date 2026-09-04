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
from escape_ai.training import PolicyValueNet, encode_state, legal_action_mask


@dataclass(frozen=True, slots=True)
class Evaluation:
    priors: npt.NDArray[np.float32]
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
            priors = np.zeros((state.size + 1) ** 2, dtype=np.float32)
            priors[actions] = probability
            results.append(Evaluation(priors, 0.0))
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
        masks = torch.from_numpy(np.stack([legal_action_mask(state) for state in states])).to(
            self.device
        )
        with torch.inference_mode():
            logits, values = self.model(batch)
            probabilities = torch.softmax(logits.masked_fill(~masks, -torch.inf), dim=1)
        probabilities_cpu = probabilities.cpu().numpy()
        values_cpu = values.cpu().numpy()

        results: list[Evaluation] = []
        for index, _state in enumerate(states):
            results.append(
                Evaluation(
                    probabilities_cpu[index].astype(np.float32, copy=True),
                    float(values_cpu[index]),
                )
            )
        return results


@dataclass(slots=True)
class SearchNode:
    state: _escape_core.State
    visits: int = 0
    children: dict[int, SearchNode] = field(default_factory=dict)
    expanded: bool = False
    legal: npt.NDArray[np.int64] = field(init=False)
    priors: npt.NDArray[np.float32] = field(init=False)
    edge_visits: npt.NDArray[np.int32] = field(init=False)
    edge_value_sums: npt.NDArray[np.float32] = field(init=False)

    def __post_init__(self) -> None:
        action_space = (self.state.size + 1) ** 2
        self.legal = np.empty(0, dtype=np.int64)
        self.priors = np.zeros(action_space, dtype=np.float32)
        self.edge_visits = np.zeros(action_space, dtype=np.int32)
        self.edge_value_sums = np.zeros(action_space, dtype=np.float32)


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
        parallel_leaves: int = 1,
        virtual_loss: float = 1.0,
    ) -> None:
        if simulations < 1 or parallel_leaves < 1:
            raise ValueError("simulations and parallel_leaves must be positive")
        self.evaluator = evaluator
        self.simulations = simulations
        self.c_puct = c_puct
        self.dirichlet_alpha = dirichlet_alpha
        self.dirichlet_fraction = dirichlet_fraction
        self.parallel_leaves = parallel_leaves
        self.virtual_loss = virtual_loss

    def run(
        self,
        state: _escape_core.State,
        rng: random.Random,
        *,
        temperature: float = 0.0,
        add_root_noise: bool = False,
        include_statistics: bool = True,
    ) -> SearchResult:
        return self.run_batch(
            [state],
            [rng],
            temperatures=[temperature],
            add_root_noise=add_root_noise,
            include_statistics=include_statistics,
        )[0]

    def run_batch(
        self,
        states: Sequence[_escape_core.State],
        rngs: Sequence[random.Random],
        *,
        temperatures: Sequence[float],
        add_root_noise: bool = False,
        include_statistics: bool = True,
    ) -> list[SearchResult]:
        """Search independent roots together so every leaf evaluation is batched."""

        if not states:
            return []
        if len(states) != len(rngs) or len(states) != len(temperatures):
            raise ValueError("states, RNGs, and temperatures must have equal lengths")
        if any(state.outcome["status"] != "playing" for state in states):
            raise ValueError("cannot search a terminal state")
        roots = [SearchNode(state) for state in states]
        initial_evaluations = self.evaluator.evaluate(states)
        if len(initial_evaluations) != len(roots):
            raise AssertionError("evaluator returned the wrong batch length")
        for root, initial_evaluation, rng in zip(roots, initial_evaluations, rngs, strict=True):
            self._expand_with_evaluation(root, initial_evaluation)
            if add_root_noise:
                self._add_root_noise(root, rng)

        completed_simulations = 0
        while completed_simulations < self.simulations:
            leaf_wave = min(
                self.parallel_leaves,
                self.simulations - completed_simulations,
            )
            leaves: list[SearchNode] = []
            paths: list[list[tuple[SearchNode, int]]] = []
            pending_indices: list[int] = []
            for root in roots:
                for _ in range(leaf_wave):
                    node = root
                    path: list[tuple[SearchNode, int]] = []
                    while node.expanded and node.legal.size:
                        action = self._select(node)
                        child = node.children.get(action)
                        if child is None:
                            child = SearchNode(node.state.apply(action))
                            node.children[action] = child
                        path.append((node, action))
                        node = child
                        if node.state.outcome["status"] != "playing":
                            break
                    self._reserve(node, path)
                    leaves.append(node)
                    paths.append(path)
                    if node.state.outcome["status"] == "playing":
                        pending_indices.append(len(leaves) - 1)

            evaluations = self.evaluator.evaluate(
                [leaves[index].state for index in pending_indices]
            )
            if len(evaluations) != len(pending_indices):
                raise AssertionError("evaluator returned the wrong batch length")
            evaluated = dict(zip(pending_indices, evaluations, strict=True))
            for index, (node, path) in enumerate(zip(leaves, paths, strict=True)):
                leaf_evaluation = evaluated.get(index)
                value = (
                    self._terminal_value(node.state)
                    if leaf_evaluation is None
                    else self._expand_with_evaluation(node, leaf_evaluation)
                )
                self._complete_backup(node, path, value)
            completed_simulations += leaf_wave

        return [
            self._result(
                root,
                temperature,
                rng,
                include_statistics=include_statistics,
            )
            for root, temperature, rng in zip(roots, temperatures, rngs, strict=True)
        ]

    def _result(
        self,
        root: SearchNode,
        temperature: float,
        rng: random.Random,
        *,
        include_statistics: bool,
    ) -> SearchResult:
        visits = np.zeros((root.state.size + 1) ** 2, dtype=np.float32)
        visits[root.legal] = root.edge_visits[root.legal]
        statistics: list[ActionStatistics] = []
        if include_statistics:
            for action_value in root.legal:
                action = int(action_value)
                edge_visits = int(root.edge_visits[action])
                mean_value = (
                    float(root.edge_value_sums[action]) / edge_visits if edge_visits else 0.0
                )
                statistics.append(
                    ActionStatistics(
                        action,
                        float(root.priors[action]),
                        edge_visits,
                        mean_value,
                    )
                )
        policy = self._visit_policy(visits, 1.0)
        selection_policy = self._visit_policy(visits, temperature)
        action = self._sample_action(selection_policy, rng)
        statistics.sort(key=lambda item: (-item.visits, item.action))
        root_value = float(root.edge_value_sums.sum()) / max(root.visits, 1)
        return SearchResult(action, policy, root_value, tuple(statistics))

    @staticmethod
    def _expand_with_evaluation(node: SearchNode, evaluation: Evaluation) -> float:
        legal = node.state.legal_actions()
        action_space = (node.state.size + 1) ** 2
        if evaluation.priors.shape != (action_space,):
            raise ValueError("evaluator policy has the wrong action-space shape")
        legal_indices = np.asarray(legal, dtype=np.int64)
        priors = np.maximum(evaluation.priors[legal_indices], 0.0)
        total = float(priors.sum())
        if not math.isfinite(total) or total <= 0.0:
            priors.fill(1.0 / len(legal))
        else:
            priors /= total
        node.legal = legal_indices
        node.priors[node.legal] = priors.astype(np.float32)
        node.expanded = True
        return evaluation.value

    @staticmethod
    def _terminal_value(state: _escape_core.State) -> float:
        winner = state.outcome["winner"]
        return 0.0 if winner is None else (1.0 if winner == state.turn else -1.0)

    def _reserve(
        self,
        node: SearchNode,
        path: Sequence[tuple[SearchNode, int]],
    ) -> None:
        node.visits += 1
        for parent, action in reversed(path):
            parent.edge_visits[action] += 1
            parent.edge_value_sums[action] -= self.virtual_loss
            parent.visits += 1

    def _complete_backup(
        self,
        node: SearchNode,
        path: Sequence[tuple[SearchNode, int]],
        value: float,
    ) -> None:
        value_player = node.state.turn
        for parent, action in reversed(path):
            parent_player = parent.state.turn
            if parent_player != value_player:
                value = -value
            parent.edge_value_sums[action] += self.virtual_loss + value
            value_player = parent_player

    def _select(self, node: SearchNode) -> int:
        scale = math.sqrt(max(node.visits, 1))
        legal_visits = node.edge_visits[node.legal]
        means = np.divide(
            node.edge_value_sums[node.legal],
            legal_visits,
            out=np.zeros(len(node.legal), dtype=np.float32),
            where=legal_visits != 0,
        )
        exploration = self.c_puct * node.priors[node.legal] * scale / (1.0 + legal_visits)
        return int(node.legal[int(np.argmax(means + exploration))])

    def _add_root_noise(self, root: SearchNode, rng: random.Random) -> None:
        if not root.legal.size or self.dirichlet_fraction <= 0.0:
            return
        noise_rng = np.random.default_rng(rng.getrandbits(64))
        noise = noise_rng.dirichlet(np.full(len(root.legal), self.dirichlet_alpha))
        keep = 1.0 - self.dirichlet_fraction
        root.priors[root.legal] = keep * root.priors[root.legal] + self.dirichlet_fraction * noise

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
