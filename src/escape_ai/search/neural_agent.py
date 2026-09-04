"""Fixed-budget neural PUCT agent for evaluation matches."""

from __future__ import annotations

import random
from dataclasses import dataclass

from escape_ai import _escape_core

from .puct import PositionEvaluator, PUCTSearch


@dataclass(frozen=True, slots=True)
class NeuralPUCTAgent:
    evaluator: PositionEvaluator
    simulations: int
    model_id: str
    c_puct: float = 1.5

    @property
    def name(self) -> str:
        return f"neural-puct:{self.model_id}"

    def select_action(self, state: _escape_core.State, rng: random.Random) -> int:
        search = PUCTSearch(
            self.evaluator,
            simulations=self.simulations,
            c_puct=self.c_puct,
        )
        return search.run(
            state,
            rng,
            temperature=0.0,
            add_root_noise=False,
            include_statistics=False,
        ).action
