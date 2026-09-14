from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import torch

from escape_ai.training.checkpoint import save_checkpoint
from escape_ai.training.lineage import (
    InitialCheckpointReference,
    _initialize_lineage_model,
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

    try:
        _initialize_lineage_model(config)
    except ValueError as error:
        assert "network does not match" in str(error)
    else:
        raise AssertionError("mismatched initial checkpoint was accepted")
