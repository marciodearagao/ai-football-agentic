import pytest
from pydantic import ValidationError

from app.domain.enums import FootballerBehavior
from app.domain.footballer import Footballer


def footballer_data() -> dict[str, object]:
    return {
        "name": "Alex Morgan",
        "skill": 82,
        "intelligence": 78,
        "stamina": 85,
    }


def test_valid_footballer_creation() -> None:
    footballer = Footballer(**footballer_data(), energy=91, behavior="PRESS")

    assert footballer.name == "Alex Morgan"
    assert footballer.skill == 82
    assert footballer.intelligence == 78
    assert footballer.stamina == 85
    assert footballer.energy == 91
    assert footballer.behavior is FootballerBehavior.PRESS


def test_energy_defaults_to_100() -> None:
    assert Footballer(**footballer_data()).energy == 100


def test_behavior_defaults_to_support() -> None:
    assert Footballer(**footballer_data()).behavior is FootballerBehavior.SUPPORT


def test_invalid_behavior_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Footballer(**footballer_data(), behavior="SHOOT")


@pytest.mark.parametrize("skill", [-1, 101])
def test_invalid_skill_is_rejected(skill: int) -> None:
    with pytest.raises(ValidationError):
        Footballer(**(footballer_data() | {"skill": skill}))


@pytest.mark.parametrize("energy", [-1, 101])
def test_invalid_energy_is_rejected(energy: int) -> None:
    with pytest.raises(ValidationError):
        Footballer(**footballer_data(), energy=energy)


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("intelligence", -1),
        ("intelligence", 101),
        ("stamina", -1),
        ("stamina", 101),
    ],
)
def test_other_bounded_attributes_reject_invalid_values(
    attribute: str, value: int
) -> None:
    with pytest.raises(ValidationError):
        Footballer(**(footballer_data() | {attribute: value}))
