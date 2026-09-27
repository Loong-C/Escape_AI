"""Read-only DuckDB/FastAPI access to analysis-grade Parquet games."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb

from escape_ai import _escape_core

if TYPE_CHECKING:
    from escape_ai.play import PlayService


class ResearchGameRepository:
    def __init__(self, source: str | Path) -> None:
        selected = Path(source)
        self.source = str(selected / "*.parquet") if selected.is_dir() else str(source)
        self.connection = duckdb.connect()

    def list_games(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, object]]:
        rows = self.connection.execute(
            """
            SELECT game_id,
                   any_value(white_model_id) white_model_id,
                   any_value(black_model_id) black_model_id,
                   any_value(board_size) board_size,
                   any_value(search_simulations) search_simulations,
                   any_value(winner) winner,
                   any_value(reason) reason,
                   max(ply) + 1 plies,
                   min(ply) FILTER (WHERE ball_moved) first_ball_move
            FROM read_parquet(?)
            GROUP BY game_id ORDER BY game_id
            LIMIT ? OFFSET ?
            """,
            [self.source, limit, offset],
        ).fetchall()
        names = (
            "game_id",
            "white_model_id",
            "black_model_id",
            "board_size",
            "search_simulations",
            "winner",
            "reason",
            "plies",
            "first_ball_move",
        )
        return [dict(zip(names, row, strict=True)) for row in rows]

    def get_game(self, game_id: str) -> dict[str, object] | None:
        cursor = self.connection.execute(
            """
            SELECT * FROM read_parquet(?)
            WHERE game_id = ? ORDER BY ply
            """,
            [self.source, game_id],
        )
        names = [item[0] for item in cursor.description]
        rows = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
        if not rows:
            return None
        first = rows[0]
        last = rows[-1]
        final_state = _escape_core.State.deserialize(last["state"]).apply(int(last["action"]))
        return {
            "game_id": game_id,
            "white_model_id": first["white_model_id"],
            "black_model_id": first["black_model_id"],
            "board_size": first["board_size"],
            "search_simulations": first["search_simulations"],
            "winner": first["winner"],
            "reason": first["reason"],
            "moves": [self._move_payload(row) for row in rows],
            "final_state": self._state_payload(final_state),
        }

    @staticmethod
    def _state_payload(state: _escape_core.State) -> dict[str, object]:
        posts = "".join(
            "." if post is None else "W" if post == "white" else "B" for post in state.posts
        )
        return {
            "size": state.size,
            "posts": posts,
            "ball": {"row": state.ball[0], "col": state.ball[1]},
            "turn": state.turn,
            "outcome": state.outcome,
            "walls": [
                {"orientation": item[0], "row": item[1], "col": item[2], "color": item[3]}
                for item in state.walls()
            ],
        }

    @staticmethod
    def _move_payload(row: Mapping[str, Any]) -> dict[str, object]:
        state = _escape_core.State.deserialize(row["state"])
        candidate_actions = row["candidate_actions"]
        candidate_priors = row["candidate_priors"]
        candidate_visits = row["candidate_visits"]
        candidate_values = row["candidate_values"]
        candidates = [
            {"action": int(action), "prior": float(prior), "visits": int(visits), "q": float(q)}
            for action, prior, visits, q in zip(
                candidate_actions,
                candidate_priors,
                candidate_visits,
                candidate_values,
                strict=True,
            )
        ]
        return {
            "ply": int(row["ply"]),
            "turn": row["turn"],
            "action": int(row["action"]),
            "move_kind": row["move_kind"],
            "root_value": float(row["root_value"]),
            "policy_entropy": float(row["policy_entropy"]),
            "state_hash": str(row["state_hash"]),
            "state": ResearchGameRepository._state_payload(state),
            "features": {
                "legal_actions": int(row["legal_actions"]),
                "first_step_costs": row["first_step_costs"],
                "directional_exit_distances": row["directional_exit_distances"],
                "unique_gradient": bool(row["unique_gradient"]),
                "gradient_delta": row["gradient_delta"],
                "white_posts": int(row["white_posts"]),
                "black_posts": int(row["black_posts"]),
                "white_floating": int(row["white_floating"]),
                "black_floating": int(row["black_floating"]),
                "white_anchored": int(row["white_anchored"]),
                "black_anchored": int(row["black_anchored"]),
                "white_walls": int(row["white_walls"]),
                "black_walls": int(row["black_walls"]),
                "new_walls": int(row["new_walls"]),
                "ball_moved": bool(row["ball_moved"]),
                "ball_move_direction": row["ball_move_direction"],
                "reply_resistance": row["reply_resistance"],
            },
            "candidates": candidates,
        }


def create_viewer_app(
    repository: ResearchGameRepository,
    viewer_dist: Path | None = None,
    play_service: PlayService | None = None,
) -> Any:
    """Create the research viewer and optional server-authoritative play API."""

    from fastapi import FastAPI, HTTPException
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(title="Escape AI Research Viewer", docs_url="/api/docs")

    @app.get("/api/games")
    def list_games(limit: int = 100, offset: int = 0) -> list[dict[str, object]]:
        return repository.list_games(limit=min(max(limit, 1), 1000), offset=max(offset, 0))

    @app.get("/api/games/{game_id}")
    def get_game(game_id: str) -> dict[str, object]:
        game = repository.get_game(game_id)
        if game is None:
            raise HTTPException(status_code=404, detail="game not found")
        return game

    @app.get("/api/play")
    def play_configuration() -> dict[str, object]:
        if play_service is None:
            return {"enabled": False, "model": None}
        return play_service.configuration()

    @app.post("/api/play/games")
    def create_play_game(payload: dict[str, object]) -> dict[str, object]:
        if play_service is None:
            raise HTTPException(status_code=503, detail="human-versus-AI play is disabled")
        human_player = payload.get("human_player")
        if human_player not in ("white", "black"):
            raise HTTPException(status_code=422, detail="human_player must be white or black")
        return play_service.create_game(human_player)

    @app.get("/api/play/games/{session_id}")
    def get_play_game(session_id: str) -> dict[str, object]:
        if play_service is None:
            raise HTTPException(status_code=503, detail="human-versus-AI play is disabled")
        try:
            return play_service.get_game(session_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="play session not found") from error

    @app.post("/api/play/games/{session_id}/moves")
    def play_human_move(session_id: str, payload: dict[str, object]) -> dict[str, object]:
        if play_service is None:
            raise HTTPException(status_code=503, detail="human-versus-AI play is disabled")
        action = payload.get("action")
        if isinstance(action, bool) or not isinstance(action, int):
            raise HTTPException(status_code=422, detail="action must be an integer")
        try:
            return play_service.play_human_action(session_id, action)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="play session not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    if viewer_dist is not None and viewer_dist.is_dir():
        app.mount("/", StaticFiles(directory=viewer_dist, html=True), name="viewer")
    return app
