import pytest
from pydantic import ValidationError

from app.domain.enums import TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team


def make_footballers(count: int, skill: float = 75) -> list[Footballer]:
    return [
        Footballer(
            name=f"Footballer {number}",
            skill=skill,
            intelligence=70,
            stamina=80,
        )
        for number in range(1, count + 1)
    ]


def test_valid_team_with_exactly_11_footballers() -> None:
    team = Team(name="Northbridge FC", footballers=make_footballers(11))

    assert len(team.footballers) == 11
    assert team.tactic is TeamTactic.BALANCED


def test_invalid_team_tactic_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Team(name="Northbridge FC", footballers=make_footballers(11), tactic="PRESS")


def test_team_with_fewer_than_11_footballers_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Team(name="Northbridge FC", footballers=make_footballers(10))


def test_team_with_more_than_11_footballers_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Team(name="Northbridge FC", footballers=make_footballers(12))


@pytest.mark.parametrize("name", ["", "   "])
def test_empty_team_name_is_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        Team(name=name, footballers=make_footballers(11))


def test_base_strength_returns_average_skill() -> None:
    footballers = make_footballers(10, skill=70)
    footballers.append(
        Footballer(name="Footballer 11", skill=92, intelligence=70, stamina=80)
    )
    team = Team(name="Northbridge FC", footballers=footballers)

    assert team.base_strength == pytest.approx(72)
