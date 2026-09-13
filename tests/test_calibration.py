import app.engine.match_engine as match_engine_module
from app.engine.probability import (
    CHANCE_PROBABILITIES,
    GOAL_PROBABILITIES,
    ProbabilityBand,
)
from scripts.calibrate_matches import (
    PROFILES,
    aggregate_scores,
    run_calibration,
    run_profile_experiment,
    temporary_goal_profile,
)


def test_calibration_aggregation_counts_all_outcomes_and_goals() -> None:
    result = aggregate_scores(
        [(1, 0), (0, 0), (2, 2), (1, 1), (0, 2), (3, 1)]
    )

    assert result.team_a_wins + result.draws + result.team_b_wins == 6
    assert result.zero_goal_matches == 1
    assert result.one_goal_matches == 1
    assert result.two_goal_matches == 2
    assert result.three_plus_goal_matches == 2
    assert result.four_plus_goal_matches == 2
    assert sum(result.scorelines.values()) == 6


def test_small_calibration_is_reproducible_and_never_calls_provider() -> None:
    first = run_calibration(12)
    repeated = run_calibration(12)

    assert first == repeated
    assert first.total_matches == 12
    assert first.provider_calls == 0
    assert first.team_a_wins + first.draws + first.team_b_wins == 12
    assert sum(first.scorelines.values()) == 12


def test_current_profile_matches_production_goal_probabilities() -> None:
    assert PROFILES["CURRENT"] == GOAL_PROBABILITIES


def test_current_and_historical_profiles_contain_intended_goal_values() -> None:
    assert PROFILES["PREVIOUS_V0_1_INITIAL"] == {
        ProbabilityBand.LOW: 0.08,
        ProbabilityBand.MODERATE_LOW: 0.12,
        ProbabilityBand.MODERATE: 0.15,
        ProbabilityBand.HIGH: 0.25,
        ProbabilityBand.VERY_HIGH: 0.35,
    }
    assert PROFILES["CONSERVATIVE_EXPERIMENT"] == {
        ProbabilityBand.LOW: 0.10,
        ProbabilityBand.MODERATE_LOW: 0.17,
        ProbabilityBand.MODERATE: 0.22,
        ProbabilityBand.HIGH: 0.32,
        ProbabilityBand.VERY_HIGH: 0.42,
    }
    assert PROFILES["CURRENT"] == {
        ProbabilityBand.LOW: 0.12,
        ProbabilityBand.MODERATE_LOW: 0.20,
        ProbabilityBand.MODERATE: 0.26,
        ProbabilityBand.HIGH: 0.36,
        ProbabilityBand.VERY_HIGH: 0.46,
    }


def test_temporary_profile_is_restored_without_mutating_production_values() -> None:
    official_values = GOAL_PROBABILITIES.copy()
    official_chances = CHANCE_PROBABILITIES.copy()
    original_engine_mapping = match_engine_module.GOAL_PROBABILITIES

    with temporary_goal_profile(PROFILES["PREVIOUS_V0_1_INITIAL"]):
        assert match_engine_module.GOAL_PROBABILITIES == PROFILES["PREVIOUS_V0_1_INITIAL"]
        assert match_engine_module.GOAL_PROBABILITIES is not original_engine_mapping
        assert GOAL_PROBABILITIES == official_values
        assert CHANCE_PROBABILITIES == official_chances

    assert match_engine_module.GOAL_PROBABILITIES is original_engine_mapping
    assert GOAL_PROBABILITIES == official_values
    assert CHANCE_PROBABILITIES == official_chances


def test_profile_experiment_is_deterministic_and_has_no_provider_calls() -> None:
    first = run_profile_experiment(10)
    repeated = run_profile_experiment(10)

    assert first == repeated
    assert set(first) == {
        "CURRENT",
        "PREVIOUS_V0_1_INITIAL",
        "CONSERVATIVE_EXPERIMENT",
    }
    assert all(result.total_matches == 10 for result in first.values())
    assert all(result.provider_calls == 0 for result in first.values())
    assert match_engine_module.GOAL_PROBABILITIES is GOAL_PROBABILITIES
