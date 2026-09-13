from enum import Enum
from random import Random

RANDOM_FACTOR_MIN = 0.90
RANDOM_FACTOR_MAX = 1.10
MINIMUM_DEFENSE = 1e-9


class ProbabilityBand(str, Enum):
    LOW = "low"
    MODERATE_LOW = "moderate_low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


GOAL_PROBABILITIES: dict[ProbabilityBand, float] = {
    ProbabilityBand.LOW: 0.12,
    ProbabilityBand.MODERATE_LOW: 0.20,
    ProbabilityBand.MODERATE: 0.26,
    ProbabilityBand.HIGH: 0.36,
    ProbabilityBand.VERY_HIGH: 0.46,
}

CHANCE_PROBABILITIES: dict[ProbabilityBand, float] = {
    ProbabilityBand.LOW: 0.20,
    ProbabilityBand.MODERATE_LOW: 0.28,
    ProbabilityBand.MODERATE: 0.35,
    ProbabilityBand.HIGH: 0.45,
    ProbabilityBand.VERY_HIGH: 0.55,
}


def controlled_random_factor(random: Random) -> float:
    return random.uniform(RANDOM_FACTOR_MIN, RANDOM_FACTOR_MAX)


def attack_ratio(effective_attack: float, effective_defense: float) -> float:
    safe_attack = max(0.0, effective_attack)
    safe_defense = max(MINIMUM_DEFENSE, effective_defense)
    return safe_attack / safe_defense


def probability_band(ratio: float) -> ProbabilityBand:
    if ratio < 0.85:
        return ProbabilityBand.LOW
    if ratio < 1.00:
        return ProbabilityBand.MODERATE_LOW
    if ratio < 1.15:
        return ProbabilityBand.MODERATE
    if ratio < 1.30:
        return ProbabilityBand.HIGH
    return ProbabilityBand.VERY_HIGH


def event_occurs(probability: float, random: Random) -> bool:
    return random.random() < probability
