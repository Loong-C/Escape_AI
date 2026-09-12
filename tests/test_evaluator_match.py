from __future__ import annotations

from pathlib import Path

from escape_ai import _escape_core
from escape_ai.research.data import write_research_shard
from escape_ai.research.evaluator_match import analyze_evaluator_match
from escape_ai.research.features import position_features, transition_features
from escape_ai.research.games import ResearchGame, ResearchMove


def _one_move_game(
    game_id: str,
    seed: int,
    white_agent: str,
    black_agent: str,
    winner: str | None,
) -> ResearchGame:
    state = _escape_core.State(3)
    after = state.apply(0)
    move = ResearchMove(
        ply=0,
        turn="white",
        state=state.serialize(),
        state_hash=state.hash(),
        action=0,
        root_value=0.0,
        policy_entropy=0.0,
        features=position_features(state),
        transition=transition_features(state, 0, after),
        candidates=(),
    )
    return ResearchGame(
        game_id=game_id,
        white_model_id=white_agent,
        black_model_id=black_agent,
        seed=seed,
        board_size=3,
        search_simulations=8,
        winner=winner,
        reason="fixture",
        moves=(move,),
    )


def test_evaluator_match_validates_reciprocal_colors_and_seed_clusters(
    tmp_path: Path,
) -> None:
    raw = "checkpoint-raw"
    d4 = "checkpoint-d4"
    games = [
        _one_move_game("seed-1-a", 1, raw, d4, "black"),
        _one_move_game("seed-1-b", 1, d4, raw, "white"),
        _one_move_game("seed-2-a", 2, raw, d4, "white"),
        _one_move_game("seed-2-b", 2, d4, raw, "black"),
        _one_move_game("seed-3-a", 3, raw, d4, "white"),
        _one_move_game("seed-3-b", 3, d4, raw, "white"),
    ]
    shard = tmp_path / "games.parquet"
    write_research_shard(shard, games)

    result = analyze_evaluator_match(str(tmp_path), tmp_path / "analysis.json")

    assert result["games"] == 6
    assert result["matched_seeds"] == 3
    assert result["valid_pairs"] == 3
    assert result["all_pairs_valid"]
    assert result["overall"] == {
        "d4_wins": 3,
        "raw_wins": 3,
        "draws": 0,
        "d4_score": 0.5,
        "decisive_d4_win_rate": 0.5,
        "decisive_wilson_95": result["overall"]["decisive_wilson_95"],
        "individual_game_exact_binomial_p_vs_half": 1.0,
    }
    paired = result["paired_inference"]
    assert paired["independent_seed_clusters"] == 3
    assert paired["d4_mean_score"] == 0.5
    assert paired["d4_pair_wins"] == 1
    assert paired["raw_pair_wins"] == 1
    assert paired["tied_pairs"] == 1
    assert paired["pair_score_counts"] == {"0.00": 1, "0.50": 1, "1.00": 1}
    assert paired["two_sided_exact_sign_p"] == 1.0
