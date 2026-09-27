"""Bounded champion inference endpoint for the existing Escape website."""

from __future__ import annotations

import hmac
import os
import threading
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from escape_ai import _escape_core
from escape_ai.play.service import PlayModelInfo, PlayService, load_champion_play_service

CHAMPION_SHA256 = "0257bbee5f97e0c163ecf64eb50160fd8f8b6189b6ac042fd52dced3b0449bf3"


class Cell(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    row: int = Field(ge=0, lt=17)
    col: int = Field(ge=0, lt=17)


class Position(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    posts: list[Literal["white", "black"] | None] = Field(min_length=324, max_length=324)
    ball: Cell
    turn: Literal["white", "black"]
    seed: int = Field(ge=0, le=2**32 - 1)


def create_production_app(service: PlayService, *, api_key: str) -> FastAPI:
    """Keep the research datasets and session API off the public inference route."""
    if len(api_key) < 32:
        raise ValueError("a production API key of at least 32 characters is required")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    gate = threading.Lock()

    def authorize(authorization: str | None) -> None:
        if not hmac.compare_digest(authorization or "", f"Bearer {api_key}"):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/health")
    def health() -> dict[str, object]:
        return service.configuration()

    @app.post("/move")
    def move(
        position: Position,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, object]:
        authorize(authorization)
        if not gate.acquire(blocking=False):
            raise HTTPException(503, "AI is busy; retry shortly", headers={"Retry-After": "2"})
        try:
            state = _escape_core.State(17)
            for action, post in enumerate(position.posts):
                if post is not None:
                    state.set_post(action // 18, action % 18, post)
            state.set_ball(position.ball.row, position.ball.col)
            state.set_turn(position.turn)
            state.adjudicate_turn_start()
            if state.outcome["status"] != "playing":
                raise HTTPException(409, "position is terminal")
            return service.choose_position(state, seed=position.seed)
        finally:
            gate.release()

    return app


def app_factory() -> Any:
    """Uvicorn factory; secrets stay in the process environment."""
    if os.environ.get("ESCAPE_DEVICE") == "onnx-cpu":
        from escape_ai.play.onnx_evaluator import OnnxEvaluator
        from escape_ai.search import D4SymmetryEnsembleEvaluator

        evaluator = OnnxEvaluator(
            Path(os.environ["ESCAPE_ONNX_MODEL"]), os.environ["ESCAPE_ONNX_SHA256"],
        )
        service = PlayService(
            D4SymmetryEnsembleEvaluator(evaluator, maximum_batch_size=256),
            PlayModelInfo(
                name="lineage-c generation 199 · D4 ensemble",
                checkpoint_sha256=CHAMPION_SHA256,
                evaluator="role-aware-d4-ensemble", board_size=17,
                simulations=512, c_puct=1.5, parallel_leaves=16, device="onnx-cpu",
            ),
        )
        return create_production_app(service, api_key=os.environ["ESCAPE_INFERENCE_KEY"])

    import torch

    torch.set_num_threads(1)
    service = load_champion_play_service(
        Path(os.environ["ESCAPE_CHAMPION_CHECKPOINT"]),
        expected_sha256=CHAMPION_SHA256,
        device=os.environ.get("ESCAPE_DEVICE", "cuda"),
    )
    return create_production_app(service, api_key=os.environ["ESCAPE_INFERENCE_KEY"])
