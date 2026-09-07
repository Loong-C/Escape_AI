from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from escape_ai.paths import ARTIFACT_ROOT_ENV, artifact_root


def test_default_artifact_root_is_e_drive(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv(ARTIFACT_ROOT_ENV, raising=False)
    assert artifact_root() == Path("E:/Escape/_AI")


def test_artifact_root_environment_override(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(ARTIFACT_ROOT_ENV, "X:/alternate")
    assert artifact_root() == Path("X:/alternate")
