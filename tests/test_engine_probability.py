from random import Random

import pytest

from app.engine.probability import (
    CHANCE_PROBABILITIES,
    GOAL_PROBABILITIES,
    RANDOM_FACTOR_MAX,
    RANDOM_FACTOR_MIN,
    ProbabilityBand,
    attack_ratio,
    controlled_random_factor,
    probability_band,
)


@pytest.mark.parametrize(
    ("ratio", "expected_band"),
    [
        (0.84, ProbabilityBand.LOW),
        (0.85, ProbabilityBand.MODERATE_LOW),
        (0.99, ProbabilityBand.MODERATE_LOW),
        (1.00, ProbabilityBand.MODERATE),
        (1.14, ProbabilityBand.MODERATE),
        (1.15, ProbabilityBand.HIGH),
        (1.29, ProbabilityBand.HIGH),
        (1.30, ProbabilityBand.VERY_HIGH),
    ],
)
def test_probability_band_boundaries(
    ratio: float, expected_band: ProbabilityBand
) -> None:
    assert probability_band(ratio) is expected_band


@pytest.mark.parametrize(
    ("band", "goal_probability", "chance_probability"),
    [
        (ProbabilityBand.LOW, 0.12, 0.20),
        (ProbabilityBand.MODERATE_LOW, 0.20, 0.28),
        (ProbabilityBand.MODERATE, 0.26, 0.35),
        (ProbabilityBand.HIGH, 0.36, 0.45),
        (ProbabilityBand.VERY_HIGH, 0.46, 0.55),
    ],
)
def test_event_probability_calibration(
    band: ProbabilityBand,
    goal_probability: float,
    chance_probability: float,
) -> None:
    assert GOAL_PROBABILITIES[band] == goal_probability
    assert CHANCE_PROBABILITIES[band] == chance_probability
    assert CHANCE_PROBABILITIES[band] > GOAL_PROBABILITIES[band]


def test_random_factor_stays_inside_controlled_range() -> None:
    random = Random(123)

    factors = [controlled_random_factor(random) for _ in range(1_000)]

    assert all(RANDOM_FACTOR_MIN <= factor <= RANDOM_FACTOR_MAX for factor in factors)


def test_same_seed_produces_same_random_sequence() -> None:
    first_random = Random(42)
    second_random = Random(42)

    first_sequence = [controlled_random_factor(first_random) for _ in range(10)]
    second_sequence = [controlled_random_factor(second_random) for _ in range(10)]

    assert first_sequence == second_sequence


def test_different_seeds_produce_different_random_sequences() -> None:
    first_random = Random(1)
    second_random = Random(2)

    first_sequence = [controlled_random_factor(first_random) for _ in range(10)]
    second_sequence = [controlled_random_factor(second_random) for _ in range(10)]

    assert first_sequence != second_sequence


def test_attack_ratio_handles_zero_defense() -> None:
    assert attack_ratio(50, 0) > 0


def test_attack_ratio_never_returns_negative_value() -> None:
    assert attack_ratio(-10, 50) == 0
