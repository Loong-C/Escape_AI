"""Server-side human-versus-AI sessions backed by the canonical rules core."""

from __future__ import annotations

import random
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from escape_ai import _escape_core
from escape_ai.search import (
    D4SymmetryEnsembleEvaluator,
    PositionEvaluator,
    PUCTSearch,
    TorchEvaluator,
)
from escape_ai.training.checkpoint import load_checkpoint
from escape_ai.training.data import sha256_file

Player = Literal["white", "black"]


class PlaySessionNotFoundError(KeyError):
    """Raised when a browser refers to an unknown or expired session."""


class IllegalHumanMoveError(ValueError):
    """Raised when the requested move is illegal or it is not the human turn."""


@dataclass(frozen=True, slots=True)
class PlayModelInfo:
    name: str
    checkpoint_sha256: str
    evaluator: str
    board_size: int
    simulations: int
    c_puct: float
    parallel_leaves: int
    device: str


@dataclass(slots=True)
class _PlaySession:
    session_id: str
    human_player: Player
    state: _escape_core.State
    rng: random.Random
    moves: list[dict[str, object]]
    last_touched: float


def state_payload(state: _escape_core.State) -> dict[str, object]:
    """Convert a C++ rules state into the viewer's stable JSON shape."""

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


class PlayService:
    """Own in-memory games and serialize access to one neural evaluator."""

    def __init__(
        self,
        evaluator: PositionEvaluator,
        model_info: PlayModelInfo,
        *,
        maximum_sessions: int = 64,
    ) -> None:
        if maximum_sessions < 1:
            raise ValueError("maximum_sessions must be positive")
        self.model_info = model_info
        self.maximum_sessions = maximum_sessions
        self._search = PUCTSearch(
            evaluator,
            simulations=model_info.simulations,
            c_puct=model_info.c_puct,
            parallel_leaves=model_info.parallel_leaves,
        )
        self._sessions: dict[str, _PlaySession] = {}
        self._lock = threading.RLock()

    def configuration(self) -> dict[str, object]:
        return {"enabled": True, "model": asdict(self.model_info)}

    def create_game(self, human_player: Player) -> dict[str, object]:
        if human_player not in ("white", "black"):
            raise ValueError("human_player must be 'white' or 'black'")
        with self._lock:
            self._evict_session_if_needed()
            session_id = uuid.uuid4().hex
            session = _PlaySession(
                session_id=session_id,
                human_player=human_player,
                state=_escape_core.State(self.model_info.board_size),
                rng=random.Random(int(session_id, 16)),
                moves=[],
                last_touched=time.monotonic(),
            )
            self._sessions[session_id] = session
            if session.state.turn != human_player:
                self._play_ai_move(session)
            return self._session_payload(session)

    def get_game(self, session_id: str) -> dict[str, object]:
        with self._lock:
            session = self._session(session_id)
            session.last_touched = time.monotonic()
            return self._session_payload(session)

    def play_human_action(self, session_id: str, action: int) -> dict[str, object]:
        with self._lock:
            session = self._session(session_id)
            state = session.state
            if state.outcome["status"] != "playing":
                raise IllegalHumanMoveError("the game has already ended")
            if state.turn != session.human_player:
                raise IllegalHumanMoveError("it is not the human player's turn")
            if not 0 <= action < (state.size + 1) ** 2:
                raise IllegalHumanMoveError("the selected action is not legal")
            move_kind = state.legal_move_kind(action)
            if move_kind is None:
                raise IllegalHumanMoveError("the selected action is not legal")
            player = state.turn
            session.state = state.apply(action)
            session.moves.append(
                {
                    "ply": state.ply,
                    "player": player,
                    "actor": "human",
                    "action": action,
                    "move_kind": move_kind,
                    "root_value": None,
                    "elapsed_ms": None,
                    "candidates": [],
                }
            )
            if session.state.outcome["status"] == "playing":
                self._play_ai_move(session)
            session.last_touched = time.monotonic()
            return self._session_payload(session)

    def _play_ai_move(self, session: _PlaySession) -> None:
        state = session.state
        if state.outcome["status"] != "playing":
            return
        if state.turn == session.human_player:
            raise AssertionError("attempted to search during the human turn")
        started = time.perf_counter()
        result = self._search.run(
            state,
            session.rng,
            temperature=0.0,
            add_root_noise=False,
            include_statistics=True,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        action = result.action
        move_kind = state.legal_move_kind(action)
        if move_kind is None:
            raise AssertionError("search returned an illegal action")
        session.state = state.apply(action)
        session.moves.append(
            {
                "ply": state.ply,
                "player": state.turn,
                "actor": "ai",
                "action": action,
                "move_kind": move_kind,
                "root_value": result.root_value,
                "elapsed_ms": elapsed_ms,
                "candidates": [
                    {
                        "action": item.action,
                        "prior": item.prior,
                        "visits": item.visits,
                        "q": item.mean_value,
                    }
                    for item in result.statistics[:8]
                ],
            }
        )

    def _session(self, session_id: str) -> _PlaySession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise PlaySessionNotFoundError(session_id) from error

    def _evict_session_if_needed(self) -> None:
        if len(self._sessions) < self.maximum_sessions:
            return
        oldest = min(self._sessions.values(), key=lambda item: item.last_touched)
        del self._sessions[oldest.session_id]

    def _session_payload(self, session: _PlaySession) -> dict[str, object]:
        state = session.state
        return {
            "session_id": session.session_id,
            "human_player": session.human_player,
            "ai_player": "black" if session.human_player == "white" else "white",
            "state": state_payload(state),
            "legal_actions": (
                state.legal_actions()
                if state.outcome["status"] == "playing" and state.turn == session.human_player
                else []
            ),
            "moves": list(session.moves),
            "model": asdict(self.model_info),
        }


def load_champion_play_service(
    checkpoint: Path,
    *,
    expected_sha256: str,
    device: str = "cuda",
    board_size: int = 17,
    simulations: int = 512,
    c_puct: float = 1.5,
    parallel_leaves: int = 16,
    maximum_batch_size: int = 256,
) -> PlayService:
    """Load the verified champion and wrap it in the stronger D4 evaluator."""

    actual_sha256 = sha256_file(checkpoint)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"checkpoint SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    model, _metadata = load_checkpoint(checkpoint, device=device)
    evaluator = D4SymmetryEnsembleEvaluator(
        TorchEvaluator(model, device),
        maximum_batch_size=maximum_batch_size,
    )
    info = PlayModelInfo(
        name="lineage-c generation 199 · D4 ensemble",
        checkpoint_sha256=actual_sha256,
        evaluator="role-aware-d4-ensemble",
        board_size=board_size,
        simulations=simulations,
        c_puct=c_puct,
        parallel_leaves=parallel_leaves,
        device=device,
    )
    return PlayService(evaluator, info)
