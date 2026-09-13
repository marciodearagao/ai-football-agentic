import pytest

from app.domain.enums import MatchPhase, TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.footballers.reactive import ReactiveFootballer
from app.footballers.tactical import TacticalFootballer
from app.match.events import BlockAdvantage
from app.match.match_controller import InvalidMatchTransition, MatchController
from app.match.phases import MATCH_BLOCKS


def make_team(name: str, skill: float = 75) -> Team:
    return Team(
        name=name,
        footballers=[
            Footballer(
                name=f"{name} Footballer {number}",
                skill=skill,
                intelligence=70,
                stamina=80,
            )
            for number in range(1, 12)
        ],
        tactic=TeamTactic.BALANCED,
    )


def decision_makers() -> list[ReactiveFootballer | TacticalFootballer]:
    return [TacticalFootballer()] * 3 + [ReactiveFootballer()] * 8


class InvalidReactiveFootballer(ReactiveFootballer):
    def choose_behavior(self, footballer, context):
        return "UNSUPPORTED"


def make_controller(seed: int = 42) -> MatchController:
    return MatchController(
        make_team("Team A", skill=78),
        make_team("Team B", skill=76),
        decision_makers(),
        decision_makers(),
        seed=seed,
    )


def test_match_blocks_preserve_exact_boundaries_and_transitions() -> None:
    assert [
        (block.start_minute, block.end_minute, block.state_minute)
        for block in MATCH_BLOCKS
    ] == [
        ("1'", "25'", 25),
        ("26'", "45+5'", 45),
        ("46'", "70'", 70),
        ("71'", "90+5'", 90),
    ]
    assert [block.next_phase for block in MATCH_BLOCKS] == [
        MatchPhase.FIRST_HYDRATION,
        MatchPhase.HALF_TIME,
        MatchPhase.SECOND_HYDRATION,
        MatchPhase.FULL_TIME,
    ]


def test_continue_before_start_is_rejected() -> None:
    with pytest.raises(InvalidMatchTransition):
        make_controller().continue_match()


def test_match_cannot_be_started_twice() -> None:
    controller = make_controller()
    controller.start()

    with pytest.raises(InvalidMatchTransition):
        controller.start()


def test_exact_valid_transition_order() -> None:
    controller = make_controller()

    observed_phases = [controller.phase]
    controller.start()
    observed_phases.append(controller.phase)
    for _ in range(3):
        controller.continue_match()
        observed_phases.append(controller.phase)

    assert observed_phases == [
        MatchPhase.NOT_STARTED,
        MatchPhase.FIRST_HYDRATION,
        MatchPhase.HALF_TIME,
        MatchPhase.SECOND_HYDRATION,
        MatchPhase.FULL_TIME,
    ]


def test_state_is_updated_after_each_block() -> None:
    controller = make_controller()
    previous_average_energy = controller.state.team_a_average_energy
    cumulative_a_score = 0
    cumulative_b_score = 0

    controller.start()
    while True:
        block = controller.completed_blocks[-1]
        cumulative_a_score += int(block.simulation.team_a_goal)
        cumulative_b_score += int(block.simulation.team_b_goal)

        assert block.state.phase is MATCH_BLOCKS[len(controller.completed_blocks) - 1].next_phase
        assert block.state.team_a_score == cumulative_a_score
        assert block.state.team_b_score == cumulative_b_score
        assert block.state.team_a_average_energy < previous_average_energy
        assert block.state.previous_block_result in {
            advantage.value for advantage in BlockAdvantage
        }
        previous_average_energy = block.state.team_a_average_energy

        if controller.phase is MatchPhase.FULL_TIME:
            break
        controller.continue_match()


def test_one_decision_maker_is_required_per_footballer() -> None:
    with pytest.raises(ValueError):
        MatchController(
            make_team("Team A"),
            make_team("Team B"),
            decision_makers()[:-1],
            decision_makers(),
        )


def test_invalid_footballer_decision_is_rejected_before_simulation() -> None:
    invalid_decisions = [InvalidReactiveFootballer()] + decision_makers()[1:]
    controller = MatchController(
        make_team("Team A"),
        make_team("Team B"),
        invalid_decisions,
        decision_makers(),
    )

    with pytest.raises(ValueError):
        controller.start()

    assert controller.completed_blocks == []
