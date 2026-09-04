"""Command-line entrypoint for validation and future research workflows."""

from __future__ import annotations

import json
import random
from dataclasses import replace

import typer

from .game import (
    GameState,
    OutcomeStatus,
    Symmetry,
    apply_action,
    create_game,
    deserialize_state,
    list_legal_moves,
    list_walls,
    serialize_state,
    transform_action,
    transform_state,
)
from .paths import ensure_artifact_layout

app = typer.Typer(no_args_is_help=True, help="Escape AI research commands")


def _canonical_position(state: GameState) -> GameState:
    return replace(state, last_move=None)


@app.command()
def init_artifacts() -> None:
    """Create the configured large-artifact directory layout."""

    layout = ensure_artifact_layout()
    typer.echo(json.dumps({name: str(path) for name, path in layout.items()}, indent=2))


@app.command()
def validate(
    games: int = typer.Option(20, min=1, help="Random games per board size"),
    sizes: str = typer.Option("3,5,9,17", help="Comma-separated odd board sizes"),
    seed: int = typer.Option(20260904, help="Deterministic validation seed"),
) -> None:
    """Run reference-engine invariants over deterministic random games."""

    selected_sizes = tuple(int(value.strip()) for value in sizes.split(","))
    rng = random.Random(seed)
    total_games = 0
    total_plies = 0

    for size in selected_sizes:
        for _ in range(games):
            state = create_game(size)
            while state.outcome.status is OutcomeStatus.PLAYING:
                moves = list_legal_moves(state)
                if not moves:
                    raise AssertionError("playing state has no legal move")
                move = rng.choice(moves)
                walls_before = set(list_walls(state))
                next_state = apply_action(state, move.action)
                if not walls_before.issubset(set(list_walls(next_state))):
                    raise AssertionError("a legal action removed an existing wall")
                if deserialize_state(serialize_state(next_state)) != _canonical_position(
                    next_state
                ):
                    raise AssertionError("state serialization did not round-trip")

                symmetry = rng.choice(tuple(Symmetry))
                transformed_before = transform_state(state, symmetry)
                transformed_action = transform_action(move.action, size, symmetry)
                transformed_after = apply_action(transformed_before, transformed_action)
                expected_after = transform_state(next_state, symmetry)
                if _canonical_position(transformed_after) != expected_after:
                    raise AssertionError(f"D4 transition mismatch for {symmetry.value}")

                state = next_state
                total_plies += 1
                if state.ply > 2 * (size + 1) ** 2:
                    raise AssertionError("game exceeded the theoretical ply bound")
            total_games += 1

    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "seed": seed,
                "sizes": selected_sizes,
                "games": total_games,
                "plies": total_plies,
            },
            indent=2,
        )
    )
