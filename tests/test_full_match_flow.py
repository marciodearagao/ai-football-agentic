import pytest

from app.domain.enums import MatchPhase
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.footballers.reactive import ReactiveFootballer
from app.footballers.tactical import TacticalFootballer
from app.match.match_controller import InvalidMatchTransition, MatchController


def make_team(name: str, skill: float) -> Team:
    return Team(
        name=name,
        footballers=[
            Footballer(
                name=f"{name} Footballer {number}",
                skill=skill,
                intelligence=70,
                stamina=75 + number,
            )
            for number in range(1, 12)
        ],
    )


def decision_makers() -> list[ReactiveFootballer | TacticalFootballer]:
    return [TacticalFootballer()] * 3 + [ReactiveFootballer()] * 8


def make_controller(seed: int) -> MatchController:
    return MatchController(
        make_team("Team A", 78),
        make_team("Team B", 76),
        decision_makers(),
        decision_makers(),
        seed=seed,
    )


def test_complete_match_reaches_full_time_after_exactly_four_blocks() -> None:
    controller = make_controller(seed=100)

    blocks = controller.run_to_full_time()

    assert controller.phase is MatchPhase.FULL_TIME
    assert len(blocks) == 4
    assert [block.state.minute for block in blocks] == [25, 45, 70, 90]
    assert controller.state.team_a_score >= 0
    assert controller.state.team_b_score >= 0
    assert all(
        0 <= footballer.energy <= 100
        for team in (controller.team_a, controller.team_b)
        for footballer in team.footballers
    )


def test_fifth_block_cannot_run() -> None:
    controller = make_controller(seed=101)
    controller.run_to_full_time()

    with pytest.raises(InvalidMatchTransition):
        controller.continue_match()


def test_same_seed_reproduces_complete_match() -> None:
    first = make_controller(seed=102)
    second = make_controller(seed=102)

    first_blocks = first.run_to_full_time()
    second_blocks = second.run_to_full_time()

    assert first_blocks == second_blocks
    assert first.state == second.state
    assert [player.energy for player in first.team_a.footballers] == [
        player.energy for player in second.team_a.footballers
    ]
    assert [player.energy for player in first.team_b.footballers] == [
        player.energy for player in second.team_b.footballers
    ]
