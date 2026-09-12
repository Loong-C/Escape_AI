from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from escape_ai import _escape_core
from escape_ai.research.analyze import analyze_research_games
from escape_ai.research.data import write_research_shard
from escape_ai.research.features import position_features, transition_features
from escape_ai.research.first_player import analyze_first_player_games
from escape_ai.research.games import (
    ResearchGame,
    ResearchMove,
    ResearchSearchConfig,
    play_research_games,
)
from escape_ai.search import D4SymmetryEnsembleEvaluator, UniformEvaluator


def test_position_and_transition_features_are_consistent() -> None:
    before = _escape_core.State(3)
    after = before.apply(0)
    features = position_features(before)
    transition = transition_features(before, 0, after)
    assert features.ball_row == 1
    assert features.ball_col == 1
    assert features.legal_actions == 16
    assert features.white_posts == features.black_posts == 0
    assert transition.move_kind == "place"
    assert transition.new_walls == 0


def test_research_games_write_queryable_parquet(tmp_path: Path) -> None:
    games = play_research_games(
        UniformEvaluator(),
        ResearchSearchConfig(board_size=3, simulations=8, parallel_leaves=4),
        seeds=[51, 52],
        white_model_id="uniform",
        game_ids=["research-a", "research-b"],
    )
    assert len(games) == 2
    assert all(game.moves for game in games)
    path = tmp_path / "research.parquet"
    summary = write_research_shard(path, games, metadata={"tier": "test"})
    assert summary.games == 2
    assert summary.moves == sum(len(game.moves) for game in games)
    table = pq.read_table(path)
    assert table.num_rows == summary.moves
    assert set(table.column_names) >= {
        "candidate_actions",
        "candidate_visits",
        "first_step_costs",
        "reply_resistance",
        "winner",
    }

    analysis_path = tmp_path / "analysis.json"
    analysis = analyze_research_games(str(path), analysis_path)
    assert analysis["overview"]["games"] == 2
    assert analysis["overview"]["moves"] == summary.moves
    assert analysis["openings"]["canonical_distinct"] >= 1
    assert analysis["openings"]["prefixes"]["1"]["games"] == 2
    assert (
        analysis["first_ball_move"]["ply_distribution"]["count"]
        + analysis["first_ball_move"]["games_without_movement"]
        == 2
    )
    assert analysis["overview"]["mean_first_ball_move"] == (
        analysis["first_ball_move"]["ply_distribution"]["mean"]
    )
    assert analysis["overview"]["median_first_ball_move"] == (
        analysis["first_ball_move"]["ply_distribution"]["median"]
    )
    assert set(analysis["phases"]) >= {"opening"}
    assert analysis["candidate_value_gaps"]["positions"] > 0
    assert analysis_path.is_file()

    directory_analysis = analyze_research_games(str(tmp_path), tmp_path / "directory.json")
    assert directory_analysis["overview"]["games"] == 2


def test_seeded_opening_exploration_produces_multiple_lines() -> None:
    games = play_research_games(
        UniformEvaluator(),
        ResearchSearchConfig(
            board_size=3,
            simulations=8,
            parallel_leaves=4,
            opening_plies=4,
            opening_temperature=1.0,
            add_root_noise=True,
        ),
        seeds=list(range(8)),
        white_model_id="uniform",
        game_ids=[f"diverse-{index}" for index in range(8)],
    )
    first_actions = {game.moves[0].action for game in games}
    assert len(first_actions) > 1


def test_research_games_can_continue_from_saved_state() -> None:
    initial = _escape_core.State(3).apply(0).apply(1)
    games = play_research_games(
        UniformEvaluator(),
        ResearchSearchConfig(board_size=3, simulations=4, parallel_leaves=2),
        seeds=[71, 72],
        white_model_id="uniform",
        game_ids=["branch-a", "branch-b"],
        initial_states=[initial, initial],
    )

    assert len(games) == 2
    assert all(game.moves[0].ply == initial.ply for game in games)
    assert all(game.moves[0].state_hash == initial.hash() for game in games)


def test_paired_starting_players_generate_role_swapped_games(tmp_path: Path) -> None:
    white_first = _escape_core.State(3)
    black_first = _escape_core.State(3)
    black_first.set_turn("black")
    evaluator = D4SymmetryEnsembleEvaluator(UniformEvaluator(), maximum_batch_size=64)
    games = play_research_games(
        evaluator,
        ResearchSearchConfig(
            board_size=3,
            simulations=8,
            parallel_leaves=4,
            opening_plies=4,
            opening_temperature=0.8,
        ),
        seeds=[17, 17],
        white_model_id="uniform-d4",
        game_ids=["white-first", "black-first"],
        initial_states=[white_first, black_first],
    )

    axis_swaps = (
        _escape_core.Symmetry.ROTATE_90,
        _escape_core.Symmetry.ROTATE_270,
        _escape_core.Symmetry.DIAGONAL_MAIN,
        _escape_core.Symmetry.DIAGONAL_ANTI,
    )
    matching = []
    for symmetry in axis_swaps:
        if len(games[0].moves) != len(games[1].moves):
            continue
        if all(
            _escape_core.State.deserialize(left.state).transformed(symmetry).serialize()
            == right.state
            and _escape_core.transform_action(left.action, 3, symmetry) == right.action
            for left, right in zip(games[0].moves, games[1].moves, strict=True)
        ):
            matching.append(symmetry)

    assert matching
    assert games[0].winner != games[1].winner
    assert games[0].reason == games[1].reason

    shard = tmp_path / "paired-starts.parquet"
    write_research_shard(shard, games)
    result = analyze_first_player_games(str(shard), tmp_path / "first-player.json")
    assert result["matched_seeds"] == 1
    assert result["mirrored_pairs"] == 1
    assert result["all_pairs_mirrored"]


def test_first_player_analysis_accepts_stabilizer_symmetry_switch(
    tmp_path: Path,
) -> None:
    def game_from_actions(
        game_id: str,
        starting_player: str,
        actions: list[int],
    ) -> ResearchGame:
        state = _escape_core.State(17)
        if starting_player == "black":
            state.set_turn("black")
        moves: list[ResearchMove] = []
        for action in actions:
            after = state.apply(action)
            moves.append(
                ResearchMove(
                    ply=state.ply,
                    turn=state.turn,
                    state=state.serialize(),
                    state_hash=state.hash(),
                    action=action,
                    root_value=0.0,
                    policy_entropy=0.0,
                    features=position_features(state),
                    transition=transition_features(state, action, after),
                    candidates=(),
                )
            )
            state = after
        return ResearchGame(
            game_id=game_id,
            white_model_id="symmetric",
            black_model_id="symmetric",
            seed=20261769,
            board_size=17,
            search_simulations=512,
            winner=None,
            reason="fixture",
            moves=tuple(moves),
        )

    # This real six-ply prefix is related by rotate_270 through ply three.  At
    # ply four a stabilizer-equivalent action representative is selected, after
    # which rotate_90 relates the trajectories.  Every transition remains D4
    # role-swapped equivalent even though no single transform covers the game.
    games = [
        game_from_actions(
            "white-first",
            "white",
            [207, 297, 116, 26, 206, 173],
        ),
        game_from_actions(
            "black-first",
            "black",
            [155, 160, 168, 163, 150, 206],
        ),
    ]
    shard = tmp_path / "stabilizer-switch.parquet"
    write_research_shard(shard, games)

    result = analyze_first_player_games(str(shard), tmp_path / "analysis.json")

    assert result["all_pairs_mirrored"]
    assert result["mirrored_pairs"] == 1
    assert result["dynamic_symmetry_pairs"] == 1
    assert result["symmetry_switches"] == 1
    assert result["symmetry_counts"] == {"dynamic": 1}
    assert result["dynamic_pairs"] == [
        {
            "seed": 20261769,
            "game_ids": ["white-first", "black-first"],
            "symmetry_segments": [
                {"ply": 0, "symmetry": "rotate_270"},
                {"ply": 4, "symmetry": "rotate_90"},
            ],
        }
    ]
