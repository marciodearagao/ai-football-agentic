import pytest
from pydantic import ValidationError

from app.domain.enums import MatchEventType, TeamTactic
from app.domain.match_state import MatchState


def match_state_data() -> dict[str, object]:
    return {
        "minute": 25,
        "team_a_score": 1,
        "team_b_score": 0,
        "team_a_tactic": TeamTactic.ATTACK,
        "team_b_tactic": TeamTactic.DEFEND,
        "team_a_strength": 78,
        "team_b_strength": 74,
        "team_a_average_energy": 88,
        "team_b_average_energy": 90,
        "previous_block_result": "Team A led the opening block.",
    }


def test_valid_match_state_creation() -> None:
    match_state = MatchState(**match_state_data())

    assert match_state.minute == 25
    assert match_state.team_a_score == 1
    assert match_state.team_b_score == 0
    assert match_state.team_a_tactic is TeamTactic.ATTACK
    assert match_state.team_b_tactic is TeamTactic.DEFEND


def test_invalid_match_state_tactic_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MatchState(**(match_state_data() | {"team_a_tactic": "PRESS"}))


def test_match_event_type_contains_only_approved_values() -> None:
    assert {event_type.value for event_type in MatchEventType} == {
        "GOAL",
        "CHANCE",
        "TACTICAL_CHANGE",
        "ENERGY_WARNING",
    }


def test_negative_minute_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MatchState(**(match_state_data() | {"minute": -1}))


@pytest.mark.parametrize("score_field", ["team_a_score", "team_b_score"])
def test_negative_score_is_rejected(score_field: str) -> None:
    with pytest.raises(ValidationError):
        MatchState(**(match_state_data() | {score_field: -1}))


@pytest.mark.parametrize(
    ("energy_field", "value"),
    [
        ("team_a_average_energy", -1),
        ("team_a_average_energy", 101),
        ("team_b_average_energy", -1),
        ("team_b_average_energy", 101),
    ],
)
def test_invalid_average_energy_is_rejected(energy_field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        MatchState(**(match_state_data() | {energy_field: value}))


@pytest.mark.parametrize(
    ("strength_field", "value"),
    [
        ("team_a_strength", -1),
        ("team_a_strength", 101),
        ("team_b_strength", -1),
        ("team_b_strength", 101),
    ],
)
def test_invalid_strength_is_rejected(strength_field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        MatchState(**(match_state_data() | {strength_field: value}))
