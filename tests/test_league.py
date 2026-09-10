from __future__ import annotations

from pathlib import Path

from escape_ai.evaluation.championship import (
    ChampionLeagueConfig,
    EntrantReference,
    allocate_matchups,
    load_champion_league_config,
    play_paired_matchup_games,
)
from escape_ai.evaluation.league import LeagueEntry, run_league, should_promote
from escape_ai.evaluation.runner import load_league_config
from escape_ai.search import GreedyAgent, RandomAgent
from escape_ai.search.puct import UniformEvaluator


def test_league_accounts_for_color_paired_matches() -> None:
    league = run_league(
        [LeagueEntry("random", RandomAgent()), LeagueEntry("greedy", GreedyAgent())],
        games_per_matchup=4,
        board_size=3,
        seed=41,
    )
    assert len(league.matches) == 1
    match = league.matches[0]
    assert match.first_wins + match.second_wins + match.draws == 4
    assert 0.0 <= match.confidence_low <= match.first_score <= match.confidence_high <= 1.0
    assert not should_promote(match)


def test_committed_smoke_league_loads() -> None:
    config = load_league_config(Path("configs/leagues/smoke-3x3-v1.yaml"))
    assert config.games_per_matchup == 8
    assert config.opponents == ("random", "greedy", "heuristic", "pure-mcts")
    assert len(config.checkpoint_sha256) == 64


def test_committed_champion_league_has_exact_paired_budget() -> None:
    config = load_champion_league_config(
        Path("configs/leagues/champion-17x17-v1.yaml")
    )
    plans = allocate_matchups(config)

    assert config.total_games == 10_000
    assert len(config.entrants) == 3
    assert sum(plan.games for plan in plans) == 10_000
    assert all(plan.games % 2 == 0 for plan in plans)
    assert max(plan.games for plan in plans) - min(plan.games for plan in plans) == 2


def test_champion_matchup_batches_complete_color_pairs() -> None:
    entrants = (
        EntrantReference("alpha", Path("alpha.pt"), "a" * 64),
        EntrantReference("beta", Path("beta.pt"), "b" * 64),
    )
    config = ChampionLeagueConfig(
        league_id="test-league",
        seed=17,
        board_size=3,
        total_games=4,
        games_per_shard=4,
        actor_batch_size=4,
        simulations=4,
        parallel_leaves=2,
        c_puct=1.5,
        opening_temperature=1.0,
        opening_plies=4,
        add_root_noise=False,
        device="cpu",
        entrants=entrants,
    )
    plan = allocate_matchups(config)[0]
    evaluator = UniformEvaluator()

    games = play_paired_matchup_games(
        {"alpha": evaluator, "beta": evaluator},
        plan,
        config,
        first_game_index=0,
        count=4,
    )

    assert len(games) == 4
    assert games[0].seed == games[1].seed
    assert games[2].seed == games[3].seed
    assert games[0].white_agent == games[1].black_agent == "alpha"
    assert games[0].black_agent == games[1].white_agent == "beta"
    assert all(game.plies == len(game.actions) for game in games)
