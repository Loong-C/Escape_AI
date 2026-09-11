from __future__ import annotations

from pathlib import Path

from escape_ai import _escape_core
from escape_ai.research.games import ResearchSearchConfig
from escape_ai.research.tactical import (
    BranchReference,
    PositionReference,
    audit_forced_branches,
    audit_root_position,
    load_tactical_audit_config,
)
from escape_ai.search import UniformEvaluator


def test_committed_tactical_audit_locks_positions_and_budgets() -> None:
    config = load_tactical_audit_config(
        Path("configs/tactics/champion-tactical-audit-17x17-v1.yaml")
    )

    assert config.run_id == "champion-tactical-audit-17x17-v1"
    assert config.positions[0].state_hash == 12347505577636488699
    assert config.positions[0].expected_directions[200] == "down"
    assert config.positions[0].budgets == (512, 2_048, 8_192, 32_768)
    assert config.branches[0].actions == (132, 116)
    assert config.branches[0].games_per_action == 64


def test_root_audit_records_target_rank_and_transition() -> None:
    state = _escape_core.State(3)
    reference = PositionReference(
        position_id="empty",
        game_id="fixture",
        ply=0,
        state_hash=state.hash(),
        expected_turn="white",
        expected_ball=state.ball,
        budgets=(4, 8),
        target_actions=(0, 1),
        expected_directions={0: None, 1: None},
    )

    result = audit_root_position(
        state,
        UniformEvaluator(),
        reference,
        c_puct=1.5,
        parallel_leaves=2,
        seed=91,
    )

    assert len(result["searches"]) == 2
    for search in result["searches"]:
        assert len(search["targets"]) == 2
        assert all(target["rank"] >= 1 for target in search["targets"])
        assert all(target["ball_direction"] is None for target in search["targets"])


def test_forced_branches_reuse_matched_seeds() -> None:
    state = _escape_core.State(3)
    reference = BranchReference(
        branch_id="matched",
        position_id="empty",
        actions=(0, 1),
        games_per_action=2,
        actor_batch_size=1,
        seed=101,
        search=ResearchSearchConfig(board_size=3, simulations=2, parallel_leaves=1),
    )

    result = audit_forced_branches(
        state,
        UniformEvaluator(),
        reference,
        run_id="fixture",
        model_id="uniform",
    )

    assert result["matched_seeds"] == [101, 102]
    assert len(result["branches"]) == 2
    for branch in result["branches"]:
        assert branch["games"] == 2
        assert [record["seed"] for record in branch["records"]] == [101, 102]
