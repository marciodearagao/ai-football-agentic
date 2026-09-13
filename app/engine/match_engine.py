from random import Random

from pydantic import BaseModel, Field

from app.domain.team import Team
from app.engine.modifiers import effective_strength
from app.engine.probability import (
    CHANCE_PROBABILITIES,
    GOAL_PROBABILITIES,
    attack_ratio,
    controlled_random_factor,
    event_occurs,
    probability_band,
)


class BlockSimulationResult(BaseModel):
    team_a_chance: bool
    team_b_chance: bool
    team_a_goal: bool
    team_b_goal: bool
    team_a_effective_attack: float = Field(ge=0)
    team_a_effective_defense: float = Field(ge=0)
    team_b_effective_attack: float = Field(ge=0)
    team_b_effective_defense: float = Field(ge=0)
    team_a_attack_ratio: float = Field(ge=0)
    team_b_attack_ratio: float = Field(ge=0)


class MatchEngine:
    def __init__(self, seed: int | None = None) -> None:
        self._random = Random(seed)

    def evaluate_block(self, team_a: Team, team_b: Team) -> BlockSimulationResult:
        team_a_attack, team_a_defense = effective_strength(team_a)
        team_b_attack, team_b_defense = effective_strength(team_b)

        team_a_ratio = attack_ratio(
            team_a_attack * controlled_random_factor(self._random),
            team_b_defense,
        )
        team_b_ratio = attack_ratio(
            team_b_attack * controlled_random_factor(self._random),
            team_a_defense,
        )

        team_a_band = probability_band(team_a_ratio)
        team_b_band = probability_band(team_b_ratio)

        return BlockSimulationResult(
            team_a_chance=event_occurs(
                CHANCE_PROBABILITIES[team_a_band], self._random
            ),
            team_b_chance=event_occurs(
                CHANCE_PROBABILITIES[team_b_band], self._random
            ),
            team_a_goal=event_occurs(GOAL_PROBABILITIES[team_a_band], self._random),
            team_b_goal=event_occurs(GOAL_PROBABILITIES[team_b_band], self._random),
            team_a_effective_attack=team_a_attack,
            team_a_effective_defense=team_a_defense,
            team_b_effective_attack=team_b_attack,
            team_b_effective_defense=team_b_defense,
            team_a_attack_ratio=team_a_ratio,
            team_b_attack_ratio=team_b_ratio,
        )
