import pytest

from app.domain.enums import FootballerBehavior, TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.engine.modifiers import (
    MAX_BEHAVIOR_ADJUSTMENT,
    behavior_modifiers,
    effective_strength,
    energy_modifier,
    tactic_modifiers,
)


def make_footballers(
    *,
    skill: float = 75,
    energy: float = 100,
    behavior: FootballerBehavior = FootballerBehavior.SUPPORT,
) -> list[Footballer]:
    return [
        Footballer(
            name=f"Footballer {number}",
            skill=skill,
            intelligence=70,
            stamina=80,
            energy=energy,
            behavior=behavior,
        )
        for number in range(1, 12)
    ]


def make_team(
    *,
    skill: float = 75,
    energy: float = 100,
    behavior: FootballerBehavior = FootballerBehavior.SUPPORT,
    tactic: TeamTactic = TeamTactic.BALANCED,
) -> Team:
    return Team(
        name="Test Team",
        footballers=make_footballers(
            skill=skill,
            energy=energy,
            behavior=behavior,
        ),
        tactic=tactic,
    )


@pytest.mark.parametrize(
    ("average_energy", "expected"),
    [
        (100, 1.00),
        (90, 1.00),
        (89, 0.97),
        (75, 0.97),
        (74, 0.92),
        (60, 0.92),
        (59, 0.85),
        (40, 0.85),
        (39, 0.75),
        (0, 0.75),
    ],
)
def test_energy_modifier_bands(average_energy: float, expected: float) -> None:
    assert energy_modifier(average_energy) == expected


@pytest.mark.parametrize(
    ("tactic", "expected"),
    [
        (TeamTactic.ATTACK, (1.08, 0.94)),
        (TeamTactic.BALANCED, (1.00, 1.00)),
        (TeamTactic.DEFEND, (0.92, 1.08)),
    ],
)
def test_tactic_modifiers(
    tactic: TeamTactic, expected: tuple[float, float]
) -> None:
    assert tactic_modifiers(tactic) == expected


def test_attack_behavior_increases_attack_contribution() -> None:
    pressing_players = make_footballers(behavior=FootballerBehavior.PRESS)
    mixed_players = pressing_players.copy()
    mixed_players[0] = mixed_players[0].model_copy(
        update={"behavior": FootballerBehavior.ATTACK}
    )

    baseline_attack, _ = behavior_modifiers(pressing_players)
    attack_with_attacker, _ = behavior_modifiers(mixed_players)

    assert attack_with_attacker > baseline_attack


def test_press_behavior_increases_defense_contribution() -> None:
    attacking_players = make_footballers(behavior=FootballerBehavior.ATTACK)
    mixed_players = attacking_players.copy()
    mixed_players[0] = mixed_players[0].model_copy(
        update={"behavior": FootballerBehavior.PRESS}
    )

    _, baseline_defense = behavior_modifiers(attacking_players)
    _, defense_with_press = behavior_modifiers(mixed_players)

    assert defense_with_press > baseline_defense


def test_conserve_energy_reduces_current_contribution() -> None:
    modifiers = behavior_modifiers(
        make_footballers(behavior=FootballerBehavior.CONSERVE_ENERGY)
    )

    assert modifiers == pytest.approx((0.90, 0.90))


@pytest.mark.parametrize(
    "behavior",
    list(FootballerBehavior),
)
def test_behavior_aggregation_stays_within_cap(
    behavior: FootballerBehavior,
) -> None:
    attack, defense = behavior_modifiers(make_footballers(behavior=behavior))

    assert 1 - MAX_BEHAVIOR_ADJUSTMENT <= attack <= 1 + MAX_BEHAVIOR_ADJUSTMENT
    assert 1 - MAX_BEHAVIOR_ADJUSTMENT <= defense <= 1 + MAX_BEHAVIOR_ADJUSTMENT


def test_identical_behaviors_produce_identical_modifiers() -> None:
    footballers = make_footballers(behavior=FootballerBehavior.SUPPORT)

    assert behavior_modifiers(footballers) == behavior_modifiers(footballers)


def test_higher_skill_produces_higher_effective_strength() -> None:
    lower_strength = effective_strength(make_team(skill=60))
    higher_strength = effective_strength(make_team(skill=80))

    assert higher_strength[0] > lower_strength[0]
    assert higher_strength[1] > lower_strength[1]


def test_lower_energy_reduces_effective_strength() -> None:
    full_energy = effective_strength(make_team(energy=100))
    lower_energy = effective_strength(make_team(energy=50))

    assert lower_energy[0] < full_energy[0]
    assert lower_energy[1] < full_energy[1]


def test_attack_tactic_increases_attack_and_reduces_defense() -> None:
    balanced = effective_strength(make_team(tactic=TeamTactic.BALANCED))
    attacking = effective_strength(make_team(tactic=TeamTactic.ATTACK))

    assert attacking[0] > balanced[0]
    assert attacking[1] < balanced[1]


def test_defend_tactic_reduces_attack_and_increases_defense() -> None:
    balanced = effective_strength(make_team(tactic=TeamTactic.BALANCED))
    defending = effective_strength(make_team(tactic=TeamTactic.DEFEND))

    assert defending[0] < balanced[0]
    assert defending[1] > balanced[1]


def test_effective_strength_uses_all_configured_modifiers() -> None:
    team = make_team(
        skill=75,
        energy=80,
        behavior=FootballerBehavior.ATTACK,
        tactic=TeamTactic.ATTACK,
    )

    attack, defense = effective_strength(team)

    assert attack == pytest.approx(75 * 0.97 * 1.08 * 1.10)
    assert defense == pytest.approx(75 * 0.97 * 0.94 * 1.00)
