from __future__ import annotations

from pathlib import Path

import torch

from escape_ai.search import UniformEvaluator
from escape_ai.training.checkpoint import load_checkpoint, save_checkpoint
from escape_ai.training.data import load_training_batch, write_training_shard
from escape_ai.training.learner import LearnerConfig, train_model
from escape_ai.training.model import NetworkConfig, PolicyValueNet
from escape_ai.training.selfplay import SelfPlayConfig, play_self_game


def test_smoke_learning_and_checkpoint_round_trip(tmp_path: Path) -> None:
    games = [
        play_self_game(
            UniformEvaluator(),
            SelfPlayConfig(board_size=3, simulations=4),
            seed=seed,
            model_id="uniform",
            game_id_factory=lambda seed=seed: f"game-{seed}",
        )
        for seed in (31, 32)
    ]
    shard = tmp_path / "replay.parquet"
    write_training_shard(shard, games)
    batch = load_training_batch([shard])
    torch.manual_seed(99)
    model = PolicyValueNet(
        NetworkConfig(channels=8, residual_blocks=1, value_channels=2, value_hidden=4)
    )
    before = {name: tensor.detach().clone() for name, tensor in model.state_dict().items()}
    optimizer, metrics = train_model(
        model,
        batch,
        LearnerConfig(steps=3, batch_size=8, use_amp=False),
        device="cpu",
        seed=99,
    )
    assert metrics.steps == 3
    assert metrics.mean_loss > 0
    assert any(not torch.equal(before[name], tensor) for name, tensor in model.state_dict().items())

    checkpoint = tmp_path / "model.pt"
    summary = save_checkpoint(
        checkpoint,
        model,
        optimizer=optimizer,
        metadata={"lineage": "test", "seed": 99},
    )
    assert summary.bytes > 0
    assert summary.model_id == summary.sha256[:16]
    restored, metadata = load_checkpoint(checkpoint)
    assert restored.config == model.config
    assert metadata == {"lineage": "test", "seed": 99}
    for name, tensor in model.state_dict().items():
        assert torch.equal(tensor.cpu(), restored.state_dict()[name])
