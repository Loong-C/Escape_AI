"""Resumable, color-paired championship leagues for neural checkpoints."""

from __future__ import annotations

import gzip
import io
import json
import math
import os
import random
import subprocess
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import torch
import yaml  # type: ignore[import-untyped]

from escape_ai import _escape_core
from escape_ai.paths import ensure_artifact_layout, require_artifact_capacity
from escape_ai.search import PUCTSearch, TorchEvaluator
from escape_ai.search.puct import PositionEvaluator
from escape_ai.training.checkpoint import load_checkpoint
from escape_ai.training.data import sha256_file

CHAMPIONSHIP_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class EntrantReference:
    agent_id: str
    path: Path
    sha256: str

    @property
    def model_id(self) -> str:
        return self.sha256[:16]


@dataclass(frozen=True, slots=True)
class ChampionLeagueConfig:
    league_id: str
    seed: int
    board_size: int
    total_games: int
    games_per_shard: int
    actor_batch_size: int
    simulations: int
    parallel_leaves: int
    c_puct: float
    opening_temperature: float
    opening_plies: int
    add_root_noise: bool
    device: str
    entrants: tuple[EntrantReference, ...]
    require_clean_worktree: bool = True


@dataclass(frozen=True, slots=True)
class MatchupPlan:
    matchup_index: int
    first_agent: str
    second_agent: str
    games: int


@dataclass(frozen=True, slots=True)
class CompetitionGame:
    game_id: str
    matchup_index: int
    game_index: int
    seed: int
    first_agent: str
    second_agent: str
    white_agent: str
    black_agent: str
    winner: str | None
    winner_agent: str | None
    reason: str
    plies: int
    actions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CompetitionShardSummary:
    path: Path
    matchup_index: int
    games: int
    plies: int
    bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ChampionLeagueResult:
    config: ChampionLeagueConfig
    git_commit: str
    champion_id: str
    champion_sha256: str
    games: int
    output: Path
    progress_path: Path


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def load_champion_league_config(path: Path) -> ChampionLeagueConfig:
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "champion league")
    if raw.get("schema_version") != CHAMPIONSHIP_SCHEMA_VERSION:
        raise ValueError("unsupported champion-league configuration schema")
    entrants = tuple(
        EntrantReference(
            agent_id=str(item["agent_id"]),
            path=Path(str(item["path"])),
            sha256=str(item["sha256"]),
        )
        for item in (_mapping(value, "entrant") for value in raw["entrants"])
    )
    config = ChampionLeagueConfig(
        league_id=str(raw["league_id"]),
        seed=int(raw["seed"]),
        board_size=int(raw["board_size"]),
        total_games=int(raw["total_games"]),
        games_per_shard=int(raw["games_per_shard"]),
        actor_batch_size=int(raw["actor_batch_size"]),
        simulations=int(raw["simulations"]),
        parallel_leaves=int(raw["parallel_leaves"]),
        c_puct=float(raw.get("c_puct", 1.5)),
        opening_temperature=float(raw.get("opening_temperature", 1.0)),
        opening_plies=int(raw.get("opening_plies", 0)),
        add_root_noise=bool(raw.get("add_root_noise", False)),
        device=str(raw.get("device", "cuda")),
        entrants=entrants,
        require_clean_worktree=bool(raw.get("require_clean_worktree", True)),
    )
    _validate_config(config)
    return config


def _validate_config(config: ChampionLeagueConfig) -> None:
    if len(config.entrants) < 2:
        raise ValueError("champion leagues require at least two entrants")
    if len({entrant.agent_id for entrant in config.entrants}) != len(config.entrants):
        raise ValueError("champion-league entrant IDs must be unique")
    if len({entrant.sha256 for entrant in config.entrants}) != len(config.entrants):
        raise ValueError("champion-league checkpoints must be unique")
    counts = (
        config.total_games,
        config.games_per_shard,
        config.actor_batch_size,
        config.simulations,
        config.parallel_leaves,
    )
    if min(counts) < 1:
        raise ValueError("champion-league counts must be positive")
    if config.total_games % 2 or config.games_per_shard % 2:
        raise ValueError("champion-league totals and shards must preserve color pairs")
    if config.actor_batch_size % 2:
        raise ValueError("champion-league actor batches must preserve color pairs")
    if config.board_size < 3 or config.board_size > 17 or config.board_size % 2 == 0:
        raise ValueError("champion-league board size must be odd and between 3 and 17")
    if config.opening_temperature < 0.0 or config.opening_plies < 0:
        raise ValueError("opening exploration settings must be non-negative")
    matchups = len(config.entrants) * (len(config.entrants) - 1) // 2
    if config.total_games // 2 < matchups:
        raise ValueError("champion league needs at least one color pair per matchup")


def allocate_matchups(config: ChampionLeagueConfig) -> tuple[MatchupPlan, ...]:
    """Distribute an exact even game budget as evenly as possible across matchups."""

    pairs = list(combinations(config.entrants, 2))
    color_pairs, remainder = divmod(config.total_games // 2, len(pairs))
    plans = tuple(
        MatchupPlan(
            matchup_index=index,
            first_agent=first.agent_id,
            second_agent=second.agent_id,
            games=2 * (color_pairs + (1 if index < remainder else 0)),
        )
        for index, (first, second) in enumerate(pairs)
    )
    if sum(plan.games for plan in plans) != config.total_games:
        raise AssertionError("matchup allocation lost games")
    return plans


def _play_wave(
    evaluators: Mapping[str, PositionEvaluator],
    plan: MatchupPlan,
    config: ChampionLeagueConfig,
    *,
    first_game_index: int,
    count: int,
) -> list[CompetitionGame]:
    if first_game_index % 2 or count % 2:
        raise ValueError("competition waves must begin and end on color-pair boundaries")
    game_indices = list(range(first_game_index, first_game_index + count))
    seeds = [
        config.seed + plan.matchup_index * 1_000_000 + game_index // 2
        for game_index in game_indices
    ]
    white_agents = [
        plan.first_agent if game_index % 2 == 0 else plan.second_agent
        for game_index in game_indices
    ]
    black_agents = [
        plan.second_agent if game_index % 2 == 0 else plan.first_agent
        for game_index in game_indices
    ]
    states = [_escape_core.State(config.board_size) for _ in game_indices]
    rngs = [random.Random(seed) for seed in seeds]
    actions: list[list[int]] = [[] for _ in game_indices]
    searches = {
        agent_id: PUCTSearch(
            evaluator,
            simulations=config.simulations,
            c_puct=config.c_puct,
            parallel_leaves=config.parallel_leaves,
        )
        for agent_id, evaluator in evaluators.items()
    }

    active = list(range(count))
    while active:
        groups: dict[str, list[int]] = {}
        for index in active:
            agent_id = white_agents[index] if states[index].turn == "white" else black_agents[index]
            groups.setdefault(agent_id, []).append(index)
        results: dict[int, int] = {}
        for agent_id, indices in groups.items():
            search_results = searches[agent_id].run_batch(
                [states[index] for index in indices],
                [rngs[index] for index in indices],
                temperatures=[
                    (
                        config.opening_temperature
                        if states[index].ply < config.opening_plies
                        else 0.0
                    )
                    for index in indices
                ],
                add_root_noise=(
                    config.add_root_noise and states[indices[0]].ply < config.opening_plies
                ),
                include_statistics=False,
            )
            results.update(
                (index, result.action)
                for index, result in zip(indices, search_results, strict=True)
            )
        next_active: list[int] = []
        for index in active:
            action = results[index]
            actions[index].append(action)
            states[index] = states[index].apply(action)
            if states[index].outcome["status"] == "playing":
                next_active.append(index)
        active = next_active

    games: list[CompetitionGame] = []
    for index, state in enumerate(states):
        winner = state.outcome["winner"]
        winner_agent = (
            None
            if winner is None
            else white_agents[index]
            if winner == "white"
            else black_agents[index]
        )
        game_index = game_indices[index]
        games.append(
            CompetitionGame(
                game_id=f"{config.league_id}-m{plan.matchup_index:02d}-{game_index:05d}",
                matchup_index=plan.matchup_index,
                game_index=game_index,
                seed=seeds[index],
                first_agent=plan.first_agent,
                second_agent=plan.second_agent,
                white_agent=white_agents[index],
                black_agent=black_agents[index],
                winner=winner,
                winner_agent=winner_agent,
                reason=str(state.outcome["reason"]),
                plies=state.ply,
                actions=tuple(actions[index]),
            )
        )
    return games


def play_paired_matchup_games(
    evaluators: Mapping[str, PositionEvaluator],
    plan: MatchupPlan,
    config: ChampionLeagueConfig,
    *,
    first_game_index: int,
    count: int,
) -> list[CompetitionGame]:
    """Play one resumable section of a matchup using batched neural inference."""

    if first_game_index % 2 or count % 2:
        raise ValueError("paired matchup sections must contain complete color pairs")
    games: list[CompetitionGame] = []
    while len(games) < count:
        wave = min(config.actor_batch_size, count - len(games))
        if wave % 2:
            wave -= 1
        if wave < 2:
            raise ValueError("actor batch is too small to preserve color pairs")
        games.extend(
            _play_wave(
                evaluators,
                plan,
                config,
                first_game_index=first_game_index + len(games),
                count=wave,
            )
        )
    return games


def _write_game_shard(
    path: Path,
    games: Sequence[CompetitionGame],
) -> CompetitionShardSummary:
    if not games:
        raise ValueError("cannot write an empty competition shard")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with (
            temporary.open("wb") as raw,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
            io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as text,
        ):
            for game in games:
                text.write(json.dumps(asdict(game), sort_keys=True, separators=(",", ":")))
                text.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return CompetitionShardSummary(
        path=path,
        matchup_index=games[0].matchup_index,
        games=len(games),
        plies=sum(game.plies for game in games),
        bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )


def _git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _empty_matchups(plans: Sequence[MatchupPlan]) -> list[dict[str, Any]]:
    return [
        {
            **asdict(plan),
            "completed_games": 0,
            "first_wins": 0,
            "second_wins": 0,
            "draws": 0,
            "total_plies": 0,
        }
        for plan in plans
    ]


def _restore_progress(
    path: Path,
    *,
    config_hash: str,
    git_commit: str,
    plans: Sequence[MatchupPlan],
) -> tuple[list[dict[str, Any]], list[CompetitionShardSummary]]:
    if not path.exists():
        return _empty_matchups(plans), []
    raw = _mapping(json.loads(path.read_text(encoding="utf-8")), "championship progress")
    if raw.get("config_sha256") != config_hash or raw.get("git_commit") != git_commit:
        raise RuntimeError("cannot resume champion league with different config or Git commit")
    matchups_raw = raw.get("matchups")
    shards_raw = raw.get("shards")
    if not isinstance(matchups_raw, list) or not isinstance(shards_raw, list):
        raise ValueError("invalid champion-league progress")
    matchups = [dict(_mapping(value, "matchup progress")) for value in matchups_raw]
    if [int(item["games"]) for item in matchups] != [plan.games for plan in plans]:
        raise RuntimeError("saved champion-league schedule differs from configuration")
    shards: list[CompetitionShardSummary] = []
    for value in shards_raw:
        item = _mapping(value, "competition shard")
        summary = CompetitionShardSummary(
            path=Path(str(item["path"])),
            matchup_index=int(item["matchup_index"]),
            games=int(item["games"]),
            plies=int(item["plies"]),
            bytes=int(item["bytes"]),
            sha256=str(item["sha256"]),
        )
        if not summary.path.is_file() or sha256_file(summary.path) != summary.sha256:
            raise RuntimeError(f"competition shard failed resume validation: {summary.path}")
        shards.append(summary)
    if sum(int(item["completed_games"]) for item in matchups) != sum(
        shard.games for shard in shards
    ):
        raise RuntimeError("competition shards do not match saved game count")
    return matchups, shards


def _wilson(score: float, games: int) -> tuple[float, float]:
    z = 1.959963984540054
    denominator = 1.0 + z**2 / games
    center = (score + z**2 / (2 * games)) / denominator
    margin = (
        z * math.sqrt(score * (1.0 - score) / games + z**2 / (4 * games**2)) / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _final_summary(
    config: ChampionLeagueConfig,
    *,
    config_path: Path,
    config_hash: str,
    git_commit: str,
    matchups: Sequence[Mapping[str, Any]],
    shards: Sequence[CompetitionShardSummary],
) -> dict[str, Any]:
    scored_matchups: list[dict[str, object]] = []
    rankings: dict[str, dict[str, Any]] = {
        entrant.agent_id: {
            "agent_id": entrant.agent_id,
            "checkpoint_sha256": entrant.sha256,
            "games": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "points": 0.0,
        }
        for entrant in config.entrants
    }
    for matchup in matchups:
        first = str(matchup["first_agent"])
        second = str(matchup["second_agent"])
        games = int(matchup["completed_games"])
        first_wins = int(matchup["first_wins"])
        second_wins = int(matchup["second_wins"])
        draws = int(matchup["draws"])
        first_score = (first_wins + 0.5 * draws) / games
        low, high = _wilson(first_score, games)
        scored_matchups.append(
            {
                **dict(matchup),
                "first_score": first_score,
                "confidence_low": low,
                "confidence_high": high,
            }
        )
        first_row = rankings[first]
        second_row = rankings[second]
        first_row["games"] = int(first_row["games"]) + games
        second_row["games"] = int(second_row["games"]) + games
        first_row["wins"] = int(first_row["wins"]) + first_wins
        first_row["losses"] = int(first_row["losses"]) + second_wins
        first_row["draws"] = int(first_row["draws"]) + draws
        first_row["points"] = float(first_row["points"]) + first_wins + 0.5 * draws
        second_row["wins"] = int(second_row["wins"]) + second_wins
        second_row["losses"] = int(second_row["losses"]) + first_wins
        second_row["draws"] = int(second_row["draws"]) + draws
        second_row["points"] = float(second_row["points"]) + second_wins + 0.5 * draws
    ranking_rows = list(rankings.values())
    for row in ranking_rows:
        row["score"] = float(row["points"]) / int(row["games"])
    ranking_rows.sort(
        key=lambda row: (-float(row["score"]), -int(row["wins"]), str(row["agent_id"]))
    )
    champion = ranking_rows[0]
    return {
        "schema_version": CHAMPIONSHIP_SCHEMA_VERSION,
        "league_id": config.league_id,
        "git_commit": git_commit,
        "config_path": str(config_path.resolve()),
        "config_sha256": config_hash,
        "completed_games": sum(int(item["completed_games"]) for item in matchups),
        "search": {
            "board_size": config.board_size,
            "simulations": config.simulations,
            "parallel_leaves": config.parallel_leaves,
            "c_puct": config.c_puct,
            "opening_temperature": config.opening_temperature,
            "opening_plies": config.opening_plies,
            "add_root_noise": config.add_root_noise,
            "paired_colors": True,
        },
        "hardware": {
            "device": config.device,
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
            "gpu": (
                torch.cuda.get_device_name(torch.device(config.device))
                if torch.device(config.device).type == "cuda" and torch.cuda.is_available()
                else None
            ),
        },
        "entrants": [
            {
                "agent_id": entrant.agent_id,
                "model_id": entrant.model_id,
                "checkpoint": str(entrant.path),
                "checkpoint_sha256": entrant.sha256,
            }
            for entrant in config.entrants
        ],
        "matchups": scored_matchups,
        "ranking": ranking_rows,
        "champion": champion,
        "shards": [{**asdict(shard), "path": str(shard.path)} for shard in shards],
    }


def run_champion_league(
    config_path: Path,
    *,
    repo_root: Path,
    progress: Callable[[str], None] | None = None,
) -> ChampionLeagueResult:
    """Run or resume an exact-budget neural championship league."""

    emit = progress or (lambda _message: None)
    config = load_champion_league_config(config_path)
    config_hash = sha256_file(config_path)
    git_commit = _git(repo_root, "rev-parse", "HEAD")
    if config.require_clean_worktree and _git(repo_root, "status", "--porcelain"):
        raise RuntimeError("formal champion leagues require a clean Git worktree")
    for entrant in config.entrants:
        if sha256_file(entrant.path) != entrant.sha256:
            raise ValueError(f"checkpoint hash mismatch: {entrant.path}")

    paths = ensure_artifact_layout()
    require_artifact_capacity(paths["root"], expected_new_bytes=5 * 1024**3)
    run_directory = paths["runs"] / config.league_id
    progress_path = run_directory / "progress.json"
    output = run_directory / "league.json"
    plans = allocate_matchups(config)
    matchups, shards = _restore_progress(
        progress_path,
        config_hash=config_hash,
        git_commit=git_commit,
        plans=plans,
    )

    models: dict[str, PositionEvaluator] = {}
    if any(int(matchup["completed_games"]) < int(matchup["games"]) for matchup in matchups):
        for entrant in config.entrants:
            model, _ = load_checkpoint(entrant.path, device=config.device)
            models[entrant.agent_id] = TorchEvaluator(model, config.device)

    started = time.perf_counter()
    for plan, matchup in zip(plans, matchups, strict=True):
        while int(matchup["completed_games"]) < plan.games:
            completed = int(matchup["completed_games"])
            count = min(config.games_per_shard, plan.games - completed)
            games = play_paired_matchup_games(
                models,
                plan,
                config,
                first_game_index=completed,
                count=count,
            )
            shard_index = sum(1 for shard in shards if shard.matchup_index == plan.matchup_index)
            shard_path = (
                paths["games"]
                / config.league_id
                / f"matchup-{plan.matchup_index:02d}"
                / f"shard-{shard_index:05d}.jsonl.gz"
            )
            if shard_path.exists():
                raise FileExistsError(f"untracked competition shard already exists: {shard_path}")
            shard = _write_game_shard(shard_path, games)
            shards.append(shard)
            matchup["completed_games"] = completed + count
            matchup["first_wins"] = int(matchup["first_wins"]) + sum(
                game.winner_agent == plan.first_agent for game in games
            )
            matchup["second_wins"] = int(matchup["second_wins"]) + sum(
                game.winner_agent == plan.second_agent for game in games
            )
            matchup["draws"] = int(matchup["draws"]) + sum(
                game.winner_agent is None for game in games
            )
            matchup["total_plies"] = int(matchup["total_plies"]) + sum(
                game.plies for game in games
            )
            _atomic_json(
                progress_path,
                {
                    "schema_version": CHAMPIONSHIP_SCHEMA_VERSION,
                    "league_id": config.league_id,
                    "git_commit": git_commit,
                    "config_path": str(config_path.resolve()),
                    "config_sha256": config_hash,
                    "entrants": [
                        {
                            "agent_id": entrant.agent_id,
                            "checkpoint_sha256": entrant.sha256,
                        }
                        for entrant in config.entrants
                    ],
                    "completed_games": sum(int(item["completed_games"]) for item in matchups),
                    "target_games": config.total_games,
                    "elapsed_seconds_this_process": time.perf_counter() - started,
                    "matchups": matchups,
                    "shards": [
                        {**asdict(item), "path": str(item.path)} for item in shards
                    ],
                },
            )
            emit(
                f"champion league {sum(int(item['completed_games']) for item in matchups)}"
                f"/{config.total_games}"
            )

    summary = _final_summary(
        config,
        config_path=config_path,
        config_hash=config_hash,
        git_commit=git_commit,
        matchups=matchups,
        shards=shards,
    )
    _atomic_json(output, summary)
    champion = _mapping(summary["champion"], "champion")
    return ChampionLeagueResult(
        config=config,
        git_commit=git_commit,
        champion_id=str(champion["agent_id"]),
        champion_sha256=str(champion["checkpoint_sha256"]),
        games=int(summary["completed_games"]),
        output=output,
        progress_path=progress_path,
    )
