"""Small CPU inference runtime retaining the original PUCT and D4 rules."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from escape_ai import _escape_core
from escape_ai.search.puct import Evaluation
from escape_ai.training.encoding import encode_state, legal_action_mask


class OnnxEvaluator:
    def __init__(self, model_path: Path, expected_sha256: str) -> None:
        import onnxruntime as ort  # type: ignore[import-untyped]

        if hashlib.sha256(model_path.read_bytes()).hexdigest() != expected_sha256:
            raise ValueError("ONNX model SHA-256 mismatch")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        self.session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"],
        )

    def evaluate(self, states: Sequence[_escape_core.State]) -> list[Evaluation]:
        if not states:
            return []
        logits, values = self.session.run(
            ["policy", "value"],
            {"board": np.stack([encode_state(state) for state in states])},
        )
        results: list[Evaluation] = []
        for state, row, value in zip(states, logits, values, strict=True):
            masked = np.where(legal_action_mask(state), row, -np.inf)
            probabilities = np.exp(masked - np.max(masked))
            probabilities /= probabilities.sum()
            results.append(Evaluation(probabilities.astype(np.float32), float(value)))
        return results
