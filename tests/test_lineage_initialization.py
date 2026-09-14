from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
import torch

from escape_ai.training.checkpoint import save_checkpoint
from escape_ai.training.lineage import (
    InitialCheckpointReference,
    _initialize_lineage_model,
    _restore_shards,
    load_lineage_config,
)
from escape_ai.training.model import NetworkConfig, PolicyValueNet


def test_lineage_can_reset_optimizer_from_verified_initial_checkpoint(
    tmp_path: Path,
) -> None:
    network = NetworkConfig(
        channels=16,
        residual_blocks=2,
        value_channels=4,
        value_hidden=16,
    )
    torch.manual_seed(123)
    source = PolicyValueNet(network)
    checkpoint_path = tmp_path / "source.pt"
    saved = save_checkpoint(checkpoint_path, source, metadata={"source": "fixture"})
    base = load_lineage_config(Path("configs/lineages/smoke-3x3-v1.yaml"))
    config = replace(
        base,
        device="cpu",
        initial_checkpoint=InitialCheckpointReference(
            checkpoint_path,
            saved.sha256,
            inherit_optimizer=False,
        ),
    )

    restored, optimizer, model_id = _initialize_lineage_model(config)

    assert optimizer is None
    assert model_id == saved.sha256[:16]
    for name, tensor in source.state_dict().items():
        assert torch.equal(tensor, restored.state_dict()[name])


def test_lineage_rejects_initial_checkpoint_with_wrong_network(tmp_path: Path) -> None:
    source = PolicyValueNet(NetworkConfig(channels=8, residual_blocks=1))
    checkpoint_path = tmp_path / "source.pt"
    saved = save_checkpoint(checkpoint_path, source)
    base = load_lineage_config(Path("configs/lineages/smoke-3x3-v1.yaml"))
    config = replace(
        base,
        device="cpu",
        initial_checkpoint=InitialCheckpointReference(checkpoint_path, saved.sha256),
    )

    with pytest.raises(ValueError, match="network does not match"):
        _initialize_lineage_model(config)


def test_lineage_resume_validates_replay_size_and_hash(tmp_path: Path) -> None:
    shard = tmp_path / "replay.parquet"
    shard.write_bytes(b"formal replay fixture")
    digest = hashlib.sha256(shard.read_bytes()).hexdigest()
    recorded = [
        {
            "path": str(shard),
            "games": 2,
            "positions": 17,
            "bytes": shard.stat().st_size,
            "sha256": digest,
        }
    ]
    assert _restore_shards(recorded)[0].sha256 == digest

    shard.write_bytes(b"tampered replay fixture")
    with pytest.raises(RuntimeError, match="size mismatch"):
        _restore_shards(recorded)
