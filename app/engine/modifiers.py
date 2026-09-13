from collections.abc import Sequence

from app.domain.enums import FootballerBehavior, TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team

MAX_BEHAVIOR_ADJUSTMENT = 0.10

TACTIC_MODIFIERS: dict[TeamTactic, tuple[float, float]] = {
    TeamTactic.ATTACK: (1.08, 0.94),
    TeamTactic.BALANCED: (1.00, 1.00),
    TeamTactic.DEFEND: (0.92, 1.08),
}

BEHAVIOR_ADJUSTMENTS: dict[FootballerBehavior, tuple[float, float]] = {
    FootballerBehavior.ATTACK: (0.03, 0.00),
    FootballerBehavior.SUPPORT: (0.02, 0.02),
    FootballerBehavior.PRESS: (0.00, 0.03),
    FootballerBehavior.CONSERVE_ENERGY: (-0.03, -0.03),
}


def energy_modifier(average_energy: float) -> float:
    if average_energy >= 90:
        return 1.00
    if average_energy >= 75:
        return 0.97
    if average_energy >= 60:
        return 0.92
    if average_energy >= 40:
        return 0.85
    return 0.75


def tactic_modifiers(tactic: TeamTactic) -> tuple[float, float]:
    return TACTIC_MODIFIERS[tactic]


def behavior_modifiers(
    footballers: Sequence[Footballer],
) -> tuple[float, float]:
    attack_adjustment = 0.0
    defense_adjustment = 0.0

    for footballer in footballers:
        attack_delta, defense_delta = BEHAVIOR_ADJUSTMENTS[footballer.behavior]
        attack_adjustment += attack_delta
        defense_adjustment += defense_delta

    attack_adjustment = _clamp_behavior_adjustment(attack_adjustment)
    defense_adjustment = _clamp_behavior_adjustment(defense_adjustment)
    return 1.0 + attack_adjustment, 1.0 + defense_adjustment


def effective_strength(team: Team) -> tuple[float, float]:
    average_energy = sum(
        footballer.energy for footballer in team.footballers
    ) / len(team.footballers)
    energy = energy_modifier(average_energy)
    tactic_attack, tactic_defense = tactic_modifiers(team.tactic)
    behavior_attack, behavior_defense = behavior_modifiers(team.footballers)

    effective_attack = (
        team.base_strength * energy * tactic_attack * behavior_attack
    )
    effective_defense = (
        team.base_strength * energy * tactic_defense * behavior_defense
    )
    return effective_attack, effective_defense


def _clamp_behavior_adjustment(adjustment: float) -> float:
    return max(-MAX_BEHAVIOR_ADJUSTMENT, min(MAX_BEHAVIOR_ADJUSTMENT, adjustment))
