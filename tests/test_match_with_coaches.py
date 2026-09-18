import json
from types import SimpleNamespace

from app.agents.coach import CoachAgent
from app.domain.enums import MatchEventType, MatchPhase, TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.footballers.reactive import ReactiveFootballer
from app.footballers.tactical import TacticalFootballer
from app.match.match_controller import MatchController


class SequencedCompletion:
    def __init__(self, tactics: list[TeamTactic]) -> None:
        self.tactics = tactics
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        tactic = self.tactics[len(self.calls)]
        self.calls.append(kwargs)
        return SimpleNamespace(
            id=f"response-{len(self.calls)}",
            model="test-model",
            usage=None,
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {"tactic": tactic.value, "reason": "Test decision."}
                        )
                    )
                )
            ],
        )


class FailingCompletion:
    def __init__(self) -> None:
        self.call_count = 0

    def __call__(self, **_):
        self.call_count += 1
        raise RuntimeError("provider unavailable")


def make_team(name: str, skill: float) -> Team:
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
    )


def decision_makers() -> list[ReactiveFootballer | TacticalFootballer]:
    return [TacticalFootballer()] * 3 + [ReactiveFootballer()] * 8


def make_coach(team_name: str, completion: SequencedCompletion) -> CoachAgent:
    return CoachAgent(
        team_name,
        api_key="test-key",
        model="test-model",
        completion_create=completion,
    )


def make_controller(
    seed: int,
    team_a_tactics: list[TeamTactic],
    team_b_tactics: list[TeamTactic],
) -> tuple[MatchController, SequencedCompletion, SequencedCompletion]:
    team_a_completion = SequencedCompletion(team_a_tactics)
    team_b_completion = SequencedCompletion(team_b_tactics)
    controller = MatchController(
        make_team("Team A", 78),
        make_team("Team B", 76),
        decision_makers(),
        decision_makers(),
        seed=seed,
        team_a_coach=make_coach("Team A", team_a_completion),
        team_b_coach=make_coach("Team B", team_b_completion),
    )
    return controller, team_a_completion, team_b_completion


def test_each_coach_is_consulted_once_before_each_block() -> None:
    balanced = [TeamTactic.BALANCED] * 4
    controller, team_a_completion, team_b_completion = make_controller(
        200, balanced, balanced
    )

    controller.run_to_full_time()

    assert len(team_a_completion.calls) == 4
    assert len(team_b_completion.calls) == 4
    assert controller.team_a_coach.decision_count == 4
    assert controller.team_b_coach.decision_count == 4
    assert controller.team_a_coach.provider_call_count == 4
    assert controller.team_b_coach.provider_call_count == 4
    assert all(
        call["tool_choice"] == "auto"
        for call in team_a_completion.calls + team_b_completion.calls
    )
    assert all(
        "team_score" not in call["messages"][1]["content"]
        for call in team_a_completion.calls + team_b_completion.calls
    )


def test_tactical_change_event_is_generated_only_when_tactic_changes() -> None:
    controller, _, _ = make_controller(
        201,
        [
            TeamTactic.ATTACK,
            TeamTactic.ATTACK,
            TeamTactic.DEFEND,
            TeamTactic.DEFEND,
        ],
        [TeamTactic.BALANCED] * 4,
    )

    blocks = controller.run_to_full_time()
    team_a_changes = [
        event
        for block in blocks
        for event in block.events
        if event.type is MatchEventType.TACTICAL_CHANGE
        and event.team_name == "Team A"
    ]

    assert len(team_a_changes) == 2
    assert (
        team_a_changes[0].previous_tactic,
        team_a_changes[0].new_tactic,
    ) == (TeamTactic.BALANCED, TeamTactic.ATTACK)
    assert (
        team_a_changes[1].previous_tactic,
        team_a_changes[1].new_tactic,
    ) == (TeamTactic.ATTACK, TeamTactic.DEFEND)


def test_same_coach_decisions_and_seed_reproduce_complete_match() -> None:
    team_a_tactics = [
        TeamTactic.ATTACK,
        TeamTactic.BALANCED,
        TeamTactic.DEFEND,
        TeamTactic.ATTACK,
    ]
    team_b_tactics = [
        TeamTactic.DEFEND,
        TeamTactic.DEFEND,
        TeamTactic.BALANCED,
        TeamTactic.ATTACK,
    ]
    first, _, _ = make_controller(202, team_a_tactics, team_b_tactics)
    second, _, _ = make_controller(202, team_a_tactics, team_b_tactics)

    assert first.run_to_full_time() == second.run_to_full_time()
    assert first.state == second.state


def test_missing_groq_configuration_does_not_prevent_full_match() -> None:
    team_a = make_team("Team A", 78)
    team_b = make_team("Team B", 76)
    team_a_coach = CoachAgent("Team A", api_key="", model="")
    team_b_coach = CoachAgent("Team B", api_key="", model="")
    controller = MatchController(
        team_a,
        team_b,
        decision_makers(),
        decision_makers(),
        seed=203,
        team_a_coach=team_a_coach,
        team_b_coach=team_b_coach,
    )

    blocks = controller.run_to_full_time()

    assert controller.phase is MatchPhase.FULL_TIME
    assert len(blocks) == 4
    assert team_a_coach.decision_count == 4
    assert team_b_coach.decision_count == 4
    assert team_a_coach.provider_call_count == 0
    assert team_b_coach.provider_call_count == 0
    assert all(
        block.team_a_coach_decision.tactic is TeamTactic.BALANCED
        and block.team_b_coach_decision.tactic is TeamTactic.BALANCED
        for block in blocks
    )


def test_provider_failure_does_not_prevent_full_match() -> None:
    team_a_completion = FailingCompletion()
    team_b_completion = FailingCompletion()
    team_a_coach = CoachAgent(
        "Team A",
        api_key="test-key",
        model="test-model",
        completion_create=team_a_completion,
    )
    team_b_coach = CoachAgent(
        "Team B",
        api_key="test-key",
        model="test-model",
        completion_create=team_b_completion,
    )
    controller = MatchController(
        make_team("Team A", 78),
        make_team("Team B", 76),
        decision_makers(),
        decision_makers(),
        seed=204,
        team_a_coach=team_a_coach,
        team_b_coach=team_b_coach,
    )

    blocks = controller.run_to_full_time()

    assert controller.phase is MatchPhase.FULL_TIME
    assert len(blocks) == 4
    assert team_a_completion.call_count == 4
    assert team_b_completion.call_count == 4
    assert team_a_coach.last_error == "provider_error"
    assert team_b_coach.last_error == "provider_error"
