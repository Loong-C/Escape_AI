"""Export the pinned champion and verify CPU evaluation equivalence."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import torch

from escape_ai import _escape_core
from escape_ai.play.onnx_evaluator import OnnxEvaluator
from escape_ai.play.production import CHAMPION_SHA256
from escape_ai.search import D4SymmetryEnsembleEvaluator, TorchEvaluator
from escape_ai.training.checkpoint import load_checkpoint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert hashlib.sha256(args.checkpoint.read_bytes()).hexdigest() == CHAMPION_SHA256
    torch.set_num_threads(1)
    model, _ = load_checkpoint(args.checkpoint, device="cpu")
    model.eval()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model, (torch.zeros(2, 6, 18, 18),), str(args.output),
        input_names=["board"], output_names=["policy", "value"],
        dynamic_axes={"board": {0: "batch"}, "policy": {0: "batch"}, "value": {0: "batch"}},
        opset_version=17, dynamo=False,
    )
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    original = D4SymmetryEnsembleEvaluator(TorchEvaluator(model, "cpu"))
    exported = D4SymmetryEnsembleEvaluator(OnnxEvaluator(args.output, digest))
    rng = random.Random(20260927)
    states = []
    for _ in range(4):
        state = _escape_core.State(17)
        for ply in range(40):
            if state.outcome["status"] != "playing":
                break
            if ply % 5 == 0:
                states.append(_escape_core.State.deserialize(state.serialize()))
            state = state.apply(rng.choice(state.legal_actions()))
    policy_error = value_error = 0.0
    for state in states:
        expected = original.evaluate([state])[0]
        actual = exported.evaluate([state])[0]
        policy_error = max(policy_error, float(np.max(np.abs(expected.priors - actual.priors))))
        value_error = max(value_error, abs(expected.value - actual.value))
        np.testing.assert_allclose(actual.priors, expected.priors, atol=2e-6, rtol=2e-4)
        np.testing.assert_allclose(actual.value, expected.value, atol=2e-5, rtol=2e-4)
    manifest = {
        "checkpoint_sha256": CHAMPION_SHA256, "onnx_sha256": digest,
        "validation_seed": 20260927, "positions": len(states),
        "maximum_policy_error": policy_error, "maximum_value_error": value_error,
        "torch": torch.__version__, "opset": 17,
    }
    args.output.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
