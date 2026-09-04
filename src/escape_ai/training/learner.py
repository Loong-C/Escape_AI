"""Policy-value optimization over materialized replay batches."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn
from torch.nn import functional as functional
from torch.utils.data import DataLoader, TensorDataset

from .data import TrainingBatch
from .model import PolicyValueNet


@dataclass(frozen=True, slots=True)
class LearnerConfig:
    steps: int = 1_000
    batch_size: int = 256
    learning_rate: float = 2e-3
    weight_decay: float = 1e-4
    gradient_clip: float = 5.0
    use_amp: bool = True


@dataclass(frozen=True, slots=True)
class LearnerMetrics:
    steps: int
    samples: int
    mean_loss: float
    mean_policy_loss: float
    mean_value_loss: float


def _validate_batch(batch: TrainingBatch) -> None:
    count = len(batch.features)
    if count == 0:
        raise ValueError("cannot train on an empty batch")
    if not (
        len(batch.policies) == count
        and len(batch.legal_masks) == count
        and len(batch.values) == count
    ):
        raise ValueError("training arrays have inconsistent row counts")
    if batch.policies.shape != batch.legal_masks.shape:
        raise ValueError("policy and legal-mask shapes differ")
    if np.any(batch.policies[~batch.legal_masks] > 1e-6):
        raise ValueError("policy target assigns mass to illegal actions")
    if not np.allclose(batch.policies.sum(axis=1), 1.0, atol=1e-5):
        raise ValueError("policy targets must be normalized")


def train_model(
    model: PolicyValueNet,
    batch: TrainingBatch,
    config: LearnerConfig,
    *,
    device: torch.device | str,
    seed: int,
) -> tuple[torch.optim.Optimizer, LearnerMetrics]:
    """Train for a fixed number of optimizer steps with deterministic sampling."""

    _validate_batch(batch)
    if config.steps < 1 or config.batch_size < 1:
        raise ValueError("learner steps and batch size must be positive")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    selected_device = torch.device(device)
    if selected_device.type == "cuda":
        torch.cuda.manual_seed_all(seed)

    dataset = TensorDataset(
        torch.from_numpy(batch.features),
        torch.from_numpy(batch.policies),
        torch.from_numpy(batch.legal_masks),
        torch.from_numpy(batch.values),
    )
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        dataset,
        batch_size=min(config.batch_size, len(dataset)),
        shuffle=True,
        generator=generator,
        num_workers=0,
        drop_last=False,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    use_amp = config.use_amp and selected_device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)  # type: ignore[attr-defined]
    model.to(selected_device)
    model.train()

    totals = np.zeros(3, dtype=np.float64)
    samples = 0
    iterator = iter(loader)
    for _ in range(config.steps):
        try:
            features, policies, legal_masks, values = next(iterator)
        except StopIteration:
            iterator = iter(loader)
            features, policies, legal_masks, values = next(iterator)
        features = features.to(selected_device)
        policies = policies.to(selected_device)
        legal_masks = legal_masks.to(selected_device)
        values = values.to(selected_device)
        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast(  # type: ignore[attr-defined]
            selected_device.type, enabled=use_amp
        ):
            logits, predictions = model(features)
            masked_logits = logits.masked_fill(~legal_masks, -torch.inf)
            log_policy = functional.log_softmax(masked_logits, dim=1)
            safe_log_policy = torch.where(legal_masks, log_policy, torch.zeros_like(log_policy))
            policy_loss = -(policies * safe_log_policy).sum(dim=1).mean()
            value_loss = functional.mse_loss(predictions, values)
            loss = policy_loss + value_loss
        if not bool(torch.isfinite(loss)):
            raise FloatingPointError("non-finite learner loss")
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        nn.utils.clip_grad_norm_(model.parameters(), config.gradient_clip)
        scaler.step(optimizer)
        scaler.update()
        totals += (float(loss.item()), float(policy_loss.item()), float(value_loss.item()))
        samples += int(features.shape[0])

    means = totals / config.steps
    if not all(math.isfinite(float(value)) for value in means):
        raise FloatingPointError("non-finite aggregate learner metrics")
    return optimizer, LearnerMetrics(
        steps=config.steps,
        samples=samples,
        mean_loss=float(means[0]),
        mean_policy_loss=float(means[1]),
        mean_value_loss=float(means[2]),
    )
