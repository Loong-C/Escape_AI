"""Neural-network training components for Escape."""

from typing import TYPE_CHECKING, Any

from .encoding import INPUT_CHANNELS, encode_state, legal_action_mask

if TYPE_CHECKING:
    from .model import NetworkConfig, PolicyValueNet


def __getattr__(name: str) -> Any:
    if name in {"NetworkConfig", "PolicyValueNet"}:
        from . import model

        return getattr(model, name)
    raise AttributeError(name)

__all__ = [
    "INPUT_CHANNELS",
    "NetworkConfig",
    "PolicyValueNet",
    "encode_state",
    "legal_action_mask",
]
