"""Command-line entrypoint for validation and future research workflows."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, replace
from itertools import combinations

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


@app.command()
def differential(
    games: int = typer.Option(5, min=1, help="Random games per board size"),
    sizes: str = typer.Option("3,5,9,17", help="Comma-separated odd board sizes"),
    seed: int = typer.Option(20260904, help="Deterministic validation seed"),
) -> None:
    """Compare Python and C++ engines over complete random games."""

    from .game.differential import run_differential_validation

    summary = run_differential_validation(
        games_per_size=games,
        sizes=tuple(int(value.strip()) for value in sizes.split(",")),
        seed=seed,
    )
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "seed": summary.seed,
                "sizes": summary.sizes,
                "games": summary.games,
                "states": summary.states,
                "plies": summary.plies,
            },
            indent=2,
        )
    )


@app.command("benchmark-baselines")
def benchmark_baselines(
    games: int = typer.Option(4, min=2, help="Games per paired matchup"),
    size: int = typer.Option(3, min=3, max=17, help="Odd board size"),
    seed: int = typer.Option(20260904, help="Deterministic tournament seed"),
    mcts_simulations: int = typer.Option(100, min=1, help="Pure-MCTS simulations per move"),
) -> None:
    """Run a deterministic round robin over the four fixed baselines."""

    from .search import (
        Agent,
        GreedyAgent,
        HeuristicAgent,
        PureMCTSAgent,
        RandomAgent,
        run_match,
    )

    if size % 2 == 0:
        raise typer.BadParameter("board size must be odd", param_hint="--size")
    if games % 2 != 0:
        raise typer.BadParameter("games must be even for color pairing", param_hint="--games")

    agents: list[Agent] = [
        RandomAgent(),
        GreedyAgent(),
        HeuristicAgent(),
        PureMCTSAgent(simulations=mcts_simulations),
    ]
    results = [
        run_match(
            first,
            second,
            games=games,
            size=size,
            seed=seed + matchup_index * 10_000,
        )
        for matchup_index, (first, second) in enumerate(combinations(agents, 2))
    ]
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "seed": seed,
                "size": size,
                "games_per_matchup": games,
                "matches": [asdict(result) for result in results],
            },
            indent=2,
        )
    )


@app.command("validate-openspiel")
def validate_openspiel(
    games: int = typer.Option(20, min=1, help="Games per board size"),
    sizes: str = typer.Option("3,5,9,17", help="Comma-separated odd board sizes"),
    seed: int = typer.Option(20260904, help="Deterministic transition seed"),
) -> None:
    """Run OpenSpiel API checks and compare its states with the C++ core."""

    from .integrations.openspiel import validate_adapter

    summary = validate_adapter(
        games_per_size=games,
        sizes=tuple(int(value.strip()) for value in sizes.split(",")),
        seed=seed,
    )
    typer.echo(json.dumps({"status": "ok", **asdict(summary)}, indent=2))


@app.command("run-experiment")
def run_training_experiment(
    config: str = typer.Option(..., help="Committed YAML experiment configuration"),
) -> None:
    """Run a provenance-complete self-play and learner experiment."""

    from pathlib import Path

    from .training.experiment import run_experiment

    repo_root = Path(__file__).resolve().parents[2]
    result = run_experiment(
        Path(config),
        repo_root=repo_root,
        progress=lambda message: typer.echo(message, err=True),
    )
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "experiment_id": result.experiment_id,
                "git_commit": result.git_commit,
                "games": result.games,
                "positions": result.positions,
                "elapsed_seconds": result.elapsed_seconds,
                "checkpoint": str(result.checkpoint.path),
                "checkpoint_sha256": result.checkpoint.sha256,
                "manifest": str(result.manifest),
            },
            indent=2,
        )
    )


@app.command("run-league")
def run_model_league(
    config: str = typer.Option(..., help="Committed YAML league configuration"),
) -> None:
    """Evaluate a hashed checkpoint in color-paired cross-play."""

    from pathlib import Path

    from .evaluation.runner import run_checkpoint_league

    repo_root = Path(__file__).resolve().parents[2]
    result = run_checkpoint_league(Path(config), repo_root=repo_root)
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "league_id": result.config.league_id,
                "git_commit": result.git_commit,
                "model_id": result.model_id,
                "matches": [asdict(match) for match in result.league.matches],
                "output": str(result.output),
            },
            indent=2,
        )
    )
