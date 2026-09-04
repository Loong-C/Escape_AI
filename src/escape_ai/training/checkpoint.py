"""Atomic, self-describing policy-value checkpoints."""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import torch

from .data import sha256_file
from .model import NetworkConfig, PolicyValueNet

CHECKPOINT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class CheckpointSummary:
    path: Path
    bytes: int
    sha256: str
    model_id: str


def save_checkpoint(
    path: Path,
    model: PolicyValueNet,
    *,
    optimizer: torch.optim.Optimizer | None = None,
    metadata: Mapping[str, object] | None = None,
) -> CheckpointSummary:
    """Atomically save weights, architecture, optional optimizer, and provenance."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "network_config": model.config.to_dict(),
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict() if optimizer is not None else None,
        "metadata": dict(metadata or {}),
    }
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        torch.save(payload, temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    digest = sha256_file(path)
    return CheckpointSummary(path, path.stat().st_size, digest, digest[:16])


def load_checkpoint(
    path: Path,
    *,
    device: torch.device | str = "cpu",
) -> tuple[PolicyValueNet, dict[str, Any]]:
    """Load a checkpoint using Torch's restricted weights-only unpickler."""

    raw = torch.load(path, map_location=device, weights_only=True)
    if not isinstance(raw, dict) or raw.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError("unsupported checkpoint schema")
    config_values = cast(dict[str, int], raw["network_config"])
    model = PolicyValueNet(NetworkConfig(**config_values))
    model.load_state_dict(cast(dict[str, Any], raw["model_state"]))
    model.to(device)
    metadata = cast(dict[str, Any], raw.get("metadata", {}))
    return model, metadata
