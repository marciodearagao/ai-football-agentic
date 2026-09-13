import pytest

from app.domain.enums import FootballerBehavior
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.match.energy import consume_team_energy, energy_loss


def make_footballer(
    *,
    stamina: float = 75,
    energy: float = 100,
    behavior: FootballerBehavior = FootballerBehavior.SUPPORT,
) -> Footballer:
    return Footballer(
        name="Test Footballer",
        skill=75,
        intelligence=70,
        stamina=stamina,
        energy=energy,
        behavior=behavior,
    )


def make_team(footballer: Footballer) -> Team:
    return Team(
        name="Energy Test FC",
        footballers=[footballer.model_copy(deep=True) for _ in range(11)],
    )


def test_energy_decreases_after_block() -> None:
    team = make_team(make_footballer())

    consume_team_energy(team)

    assert all(footballer.energy < 100 for footballer in team.footballers)


def test_higher_stamina_loses_less_energy() -> None:
    low_stamina = make_footballer(stamina=30)
    high_stamina = make_footballer(stamina=90)

    assert energy_loss(high_stamina) < energy_loss(low_stamina)


@pytest.mark.parametrize(
    "behavior",
    [FootballerBehavior.ATTACK, FootballerBehavior.PRESS],
)
def test_high_intensity_behavior_drains_more_than_support(
    behavior: FootballerBehavior,
) -> None:
    support_loss = energy_loss(make_footballer(behavior=FootballerBehavior.SUPPORT))
    intense_loss = energy_loss(make_footballer(behavior=behavior))

    assert intense_loss > support_loss


def test_conserve_energy_drains_less_than_support() -> None:
    support_loss = energy_loss(make_footballer(behavior=FootballerBehavior.SUPPORT))
    conserve_loss = energy_loss(
        make_footballer(behavior=FootballerBehavior.CONSERVE_ENERGY)
    )

    assert conserve_loss < support_loss


def test_energy_never_becomes_negative() -> None:
    team = make_team(make_footballer(energy=1, stamina=0))

    consume_team_energy(team)

    assert all(footballer.energy == 0 for footballer in team.footballers)
