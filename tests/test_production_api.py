from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from escape_ai import _escape_core
from escape_ai.play import PlayModelInfo, PlayService
from escape_ai.play.production import create_production_app
from escape_ai.search import UniformEvaluator

KEY = "test-only-key-" + "x" * 32


def service() -> PlayService:
    return PlayService(
        UniformEvaluator(),
        PlayModelInfo("test", "0" * 64, "uniform", 17, 4, 1.5, 2, "cpu"),
    )


def position() -> dict[str, object]:
    return {"posts": [None] * 324, "ball": {"row": 8, "col": 8}, "turn": "white", "seed": 1}


def test_api_requires_proxy_secret_and_returns_legal_move() -> None:
    client = TestClient(create_production_app(service(), api_key=KEY))
    assert client.get("/health").json()["model"]["board_size"] == 17
    assert client.post("/move", json=position()).status_code == 401
    response = client.post("/move", json=position(), headers={"Authorization": f"Bearer {KEY}"})
    assert response.status_code == 200
    move = response.json()["move"]
    state = _escape_core.State(17)
    assert state.legal_move_kind(move["row"] * 18 + move["col"]) == move["kind"]
    assert client.get("/api/games").status_code == 404


@pytest.mark.parametrize("changes", [
    {"posts": []}, {"posts": ["red"] * 324}, {"ball": {"row": -1, "col": 8}},
    {"ball": {"row": True, "col": 8}}, {"turn": "red"}, {"seed": -1},
    {"simulations": 1000000},
])
def test_invalid_positions_never_reach_cpp(changes: dict[str, object]) -> None:
    client = TestClient(create_production_app(service(), api_key=KEY))
    response = client.post(
        "/move", json=position() | changes, headers={"Authorization": f"Bearer {KEY}"},
    )
    assert response.status_code == 422


def test_concurrent_inference_is_rejected_without_unbounded_queue(monkeypatch) -> None:
    engine = service()
    entered = threading.Event()
    release = threading.Event()
    original = engine.choose_position

    def slow_move(state, *, seed):
        entered.set()
        assert release.wait(5)
        return original(state, seed=seed)

    monkeypatch.setattr(engine, "choose_position", slow_move)
    client = TestClient(create_production_app(engine, api_key=KEY))

    def request():
        return client.post("/move", json=position(), headers={"Authorization": f"Bearer {KEY}"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(request)
        try:
            assert entered.wait(5)
            assert request().status_code == 503
        finally:
            release.set()
        assert pending.result().status_code == 200
