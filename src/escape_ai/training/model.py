"""Fully convolutional AlphaZero-style policy-value network."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import cast

from torch import Tensor, nn

from .encoding import INPUT_CHANNELS


@dataclass(frozen=True, slots=True)
class NetworkConfig:
    input_channels: int = INPUT_CHANNELS
    channels: int = 64
    residual_blocks: int = 6
    value_channels: int = 16
    value_hidden: int = 128

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


class ResidualBlock(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        groups = min(8, channels)
        while channels % groups != 0:
            groups -= 1
        self.body = nn.Sequential(
            nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False),
            nn.GroupNorm(groups, channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False),
            nn.GroupNorm(groups, channels),
        )
        self.activation = nn.ReLU(inplace=True)

    def forward(self, inputs: Tensor) -> Tensor:
        return cast(Tensor, self.activation(inputs + self.body(inputs)))


class PolicyValueNet(nn.Module):
    """Shared residual trunk with spatial policy and pooled value heads."""

    def __init__(self, config: NetworkConfig | None = None) -> None:
        super().__init__()
        self.config = config or NetworkConfig()
        channels = self.config.channels
        groups = min(8, channels)
        while channels % groups != 0:
            groups -= 1
        self.stem = nn.Sequential(
            nn.Conv2d(
                self.config.input_channels,
                channels,
                kernel_size=3,
                padding=1,
                bias=False,
            ),
            nn.GroupNorm(groups, channels),
            nn.ReLU(inplace=True),
        )
        self.trunk = nn.Sequential(
            *(ResidualBlock(channels) for _ in range(self.config.residual_blocks))
        )
        self.policy_head = nn.Sequential(
            nn.Conv2d(channels, 2, kernel_size=1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(2, 1, kernel_size=1),
        )
        self.value_features = nn.Sequential(
            nn.Conv2d(channels, self.config.value_channels, kernel_size=1, bias=False),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.value_head = nn.Sequential(
            nn.Linear(self.config.value_channels, self.config.value_hidden),
            nn.ReLU(inplace=True),
            nn.Linear(self.config.value_hidden, 1),
            nn.Tanh(),
        )

    def forward(self, inputs: Tensor) -> tuple[Tensor, Tensor]:
        features = self.trunk(self.stem(inputs))
        policy_logits = self.policy_head(features).flatten(start_dim=1)
        value_features = self.value_features(features).flatten(start_dim=1)
        values = self.value_head(value_features).squeeze(1)
        return policy_logits, values
