from app.domain.enums import FootballerBehavior, MatchEventType, MatchPhase
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.engine.match_engine import BlockSimulationResult
from app.match.energy import consume_team_energy
from app.match.events import create_block_events, score_after_block


def make_result(
    *,
    team_a_chance: bool = False,
    team_b_chance: bool = False,
    team_a_goal: bool = False,
    team_b_goal: bool = False,
) -> BlockSimulationResult:
    return BlockSimulationResult(
        team_a_chance=team_a_chance,
        team_b_chance=team_b_chance,
        team_a_goal=team_a_goal,
        team_b_goal=team_b_goal,
        team_a_effective_attack=75,
        team_a_effective_defense=75,
        team_b_effective_attack=75,
        team_b_effective_defense=75,
        team_a_attack_ratio=1,
        team_b_attack_ratio=1,
    )


def make_team(name: str, energy: float = 100) -> Team:
    return Team(
        name=name,
        footballers=[
            Footballer(
                name=f"{name} Footballer {number}",
                skill=75,
                intelligence=70,
                stamina=75,
                energy=energy,
                behavior=FootballerBehavior.SUPPORT,
            )
            for number in range(1, 12)
        ],
    )


def test_goal_changes_score() -> None:
    assert score_after_block(1, 2, make_result(team_a_goal=True)) == (2, 2)


def test_chance_does_not_change_score() -> None:
    assert score_after_block(1, 2, make_result(team_a_chance=True)) == (1, 2)


def test_energy_warning_occurs_only_when_threshold_is_crossed() -> None:
    team_a = make_team("Team A", energy=45)
    team_b = make_team("Team B")

    first_warnings = consume_team_energy(team_a)
    first_events = create_block_events(
        make_result(),
        team_a,
        team_b,
        MatchPhase.FIRST_BLOCK,
        "25'",
        first_warnings,
        [],
    )
    second_warnings = consume_team_energy(team_a)
    second_events = create_block_events(
        make_result(),
        team_a,
        team_b,
        MatchPhase.SECOND_BLOCK,
        "45+5'",
        second_warnings,
        [],
    )

    assert len(first_warnings) == 11
    assert all(event.type is MatchEventType.ENERGY_WARNING for event in first_events)
    assert second_warnings == []
    assert second_events == []


def test_only_approved_event_types_are_generated() -> None:
    team_a = make_team("Team A")
    team_b = make_team("Team B")
    events = create_block_events(
        make_result(
            team_a_chance=True,
            team_b_chance=True,
            team_a_goal=True,
            team_b_goal=True,
        ),
        team_a,
        team_b,
        MatchPhase.FIRST_BLOCK,
        "25'",
        [],
        [],
    )

    assert {event.type for event in events} == {
        MatchEventType.CHANCE,
        MatchEventType.GOAL,
    }
    assert all(event.type in MatchEventType for event in events)
