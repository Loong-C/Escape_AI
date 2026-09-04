from __future__ import annotations

from pathlib import Path

from escape_ai.evaluation.league import LeagueEntry, run_league, should_promote
from escape_ai.evaluation.runner import load_league_config
from escape_ai.search import GreedyAgent, RandomAgent


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
