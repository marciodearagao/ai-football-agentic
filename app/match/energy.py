from app.domain.enums import FootballerBehavior
from app.domain.footballer import Footballer
from app.domain.team import Team

BASE_BLOCK_DRAIN = 12.0
ENERGY_WARNING_THRESHOLD = 40.0

BEHAVIOR_ENERGY_FACTORS: dict[FootballerBehavior, float] = {
    FootballerBehavior.ATTACK: 1.15,
    FootballerBehavior.SUPPORT: 1.00,
    FootballerBehavior.PRESS: 1.20,
    FootballerBehavior.CONSERVE_ENERGY: 0.65,
}


def energy_loss(footballer: Footballer) -> float:
    stamina_factor = 1.20 - (footballer.stamina / 250)
    behavior_factor = BEHAVIOR_ENERGY_FACTORS[footballer.behavior]
    return BASE_BLOCK_DRAIN * stamina_factor * behavior_factor


def consume_team_energy(team: Team) -> list[Footballer]:
    crossed_threshold: list[Footballer] = []

    for footballer in team.footballers:
        previous_energy = footballer.energy
        footballer.energy = max(0.0, min(100.0, previous_energy - energy_loss(footballer)))
        if (
            previous_energy >= ENERGY_WARNING_THRESHOLD
            and footballer.energy < ENERGY_WARNING_THRESHOLD
        ):
            crossed_threshold.append(footballer)

    return crossed_threshold
