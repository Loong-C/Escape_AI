"""Machine-local storage paths and safety limits."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ARTIFACT_ROOT_ENV = "ESCAPE_AI_ARTIFACT_ROOT"
DEFAULT_ARTIFACT_ROOT = Path("G:/Escape/_AI")
ARTIFACT_SUBDIRECTORIES = ("cache", "checkpoints", "games", "replay", "runs")
DEFAULT_MAXIMUM_BYTES = 400 * 1024**3
DEFAULT_MINIMUM_FREE_BYTES = 80 * 1024**3


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


def artifact_bytes(root: Path) -> int:
    """Return allocated file bytes below an artifact root."""

    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def require_artifact_capacity(
    root: Path,
    *,
    expected_new_bytes: int = 0,
    maximum_bytes: int = DEFAULT_MAXIMUM_BYTES,
    minimum_free_bytes: int = DEFAULT_MINIMUM_FREE_BYTES,
) -> None:
    """Stop new work before exceeding the project or disk-space safety limits."""

    used = artifact_bytes(root)
    free = shutil.disk_usage(root).free
    if used + expected_new_bytes > maximum_bytes:
        raise RuntimeError(
            f"artifact budget would exceed {maximum_bytes} bytes "
            f"(used={used}, expected={expected_new_bytes})"
        )
    if free - expected_new_bytes < minimum_free_bytes:
        raise RuntimeError(
            f"disk free-space floor would be crossed: free={free}, "
            f"expected={expected_new_bytes}, floor={minimum_free_bytes}"
        )
