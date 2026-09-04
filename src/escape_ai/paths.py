"""Machine-local storage paths and safety limits."""

from __future__ import annotations

import os
from pathlib import Path

ARTIFACT_ROOT_ENV = "ESCAPE_AI_ARTIFACT_ROOT"
DEFAULT_ARTIFACT_ROOT = Path("G:/Escape/_AI")
ARTIFACT_SUBDIRECTORIES = ("cache", "checkpoints", "games", "replay", "runs")


def artifact_root() -> Path:
    """Return the configured large-artifact root without creating it."""

    configured = os.environ.get(ARTIFACT_ROOT_ENV)
    return Path(configured) if configured else DEFAULT_ARTIFACT_ROOT


def ensure_artifact_layout(root: Path | None = None) -> dict[str, Path]:
    """Create and return the standard large-artifact directory layout."""

    selected = root if root is not None else artifact_root()
    selected.mkdir(parents=True, exist_ok=True)
    result = {"root": selected}
    for name in ARTIFACT_SUBDIRECTORIES:
        path = selected / name
        path.mkdir(exist_ok=True)
        result[name] = path
    return result

