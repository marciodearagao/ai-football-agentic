import json
from types import SimpleNamespace

import pytest

from app.agents.coach import CoachAgent
from app.domain.enums import FootballerBehavior, MatchPhase, TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.engine.modifiers import behavior_modifiers
from app.footballers.cognitive import CognitiveFootballer
from app.footballers.reactive import ReactiveFootballer
from app.footballers.tactical import TacticalFootballer
from app.match.match_controller import MatchController
from scripts.run_match import create_decision_makers, create_team


class StaticCompletion:
    def __init__(self, field: str, value: str) -> None:
        self.field = field
        self.value = value
        self.call_count = 0

    def __call__(self, **_):
        self.call_count += 1
        return SimpleNamespace(
            id=f"response-{self.call_count}",
            model="test-model",
            usage=None,
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {self.field: self.value, "reason": "Test decision."}
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
                intelligence=75,
                stamina=80,
            )
            for number in range(1, 12)
        ],
    )


def make_coach(name: str, completion) -> CoachAgent:
    return CoachAgent(
        name,
        api_key="test-key",
        model="test-model",
        completion_create=completion,
    )


def make_cognitive(name: str, completion) -> CognitiveFootballer:
    return CognitiveFootballer(
        name,
        api_key="test-key",
        model="test-model",
        completion_create=completion,
    )


def decision_makers(
    cognitive: CognitiveFootballer,
) -> list[ReactiveFootballer | TacticalFootballer | CognitiveFootballer]:
    return [
        cognitive,
        *[TacticalFootballer() for _ in range(3)],
        *[ReactiveFootballer() for _ in range(7)],
    ]


def make_controller(
    seed: int,
    cognitive_behavior: FootballerBehavior = FootballerBehavior.SUPPORT,
) -> tuple[MatchController, CognitiveFootballer, CognitiveFootballer]:
    team_a = make_team("Team A", 78)
    team_b = make_team("Team B", 76)
    team_a_cognitive = make_cognitive(
        team_a.footballers[0].name,
        StaticCompletion("behavior", cognitive_behavior.value),
    )
    team_b_cognitive = make_cognitive(
        team_b.footballers[0].name,
        StaticCompletion("behavior", cognitive_behavior.value),
    )
    controller = MatchController(
        team_a,
        team_b,
        decision_makers(team_a_cognitive),
        decision_makers(team_b_cognitive),
        seed=seed,
        team_a_coach=make_coach(
            team_a.name,
            StaticCompletion("tactic", TeamTactic.BALANCED.value),
        ),
        team_b_coach=make_coach(
            team_b.name,
            StaticCompletion("tactic", TeamTactic.BALANCED.value),
        ),
    )
    return controller, team_a_cognitive, team_b_cognitive


def test_sample_teams_have_exactly_one_cognitive_footballer_each() -> None:
    for team in (
        create_team("AI United", skill=78, stamina=78),
        create_team("Neural FC", skill=76, stamina=80),
    ):
        makers = create_decision_makers(team)
        assert sum(isinstance(maker, CognitiveFootballer) for maker in makers) == 1


def test_more_than_one_cognitive_footballer_per_team_is_rejected() -> None:
    team_a = make_team("Team A", 78)
    team_b = make_team("Team B", 76)
    cognitive_a = CognitiveFootballer(team_a.footballers[0].name, api_key="", model="")
    cognitive_b = CognitiveFootballer(team_a.footballers[1].name, api_key="", model="")
    too_many_cognitive = [
        cognitive_a,
        cognitive_b,
        *[ReactiveFootballer() for _ in range(9)],
    ]

    with pytest.raises(ValueError):
        MatchController(
            team_a,
            team_b,
            too_many_cognitive,
            [ReactiveFootballer() for _ in range(11)],
        )


def test_llm_call_limits_are_respected_for_complete_match() -> None:
    controller, team_a_cognitive, team_b_cognitive = make_controller(seed=300)

    blocks = controller.run_to_full_time()

    cognitive_calls = (
        team_a_cognitive.provider_call_count + team_b_cognitive.provider_call_count
    )
    coach_calls = (
        controller.team_a_coach.provider_call_count
        + controller.team_b_coach.provider_call_count
    )
    assert len(blocks) == 4
    assert team_a_cognitive.decision_count == 4
    assert team_b_cognitive.decision_count == 4
    assert cognitive_calls == 8
    assert coach_calls == 8
    assert cognitive_calls + coach_calls == 16


def test_cognitive_behavior_reaches_existing_engine_modifiers() -> None:
    controller, _, _ = make_controller(
        seed=301,
        cognitive_behavior=FootballerBehavior.ATTACK,
    )

    controller.start()

    assert controller.team_a.footballers[0].behavior is FootballerBehavior.ATTACK
    attack_modifier, _ = behavior_modifiers(controller.team_a.footballers)
    without_cognitive_attack = [
        footballer.model_copy(update={"behavior": FootballerBehavior.PRESS})
        for footballer in controller.team_a.footballers
    ]
    baseline_modifier, _ = behavior_modifiers(without_cognitive_attack)
    assert attack_modifier > baseline_modifier


def test_mocked_responses_and_seed_reproduce_complete_match() -> None:
    first, _, _ = make_controller(seed=302, cognitive_behavior=FootballerBehavior.PRESS)
    second, _, _ = make_controller(seed=302, cognitive_behavior=FootballerBehavior.PRESS)

    assert first.run_to_full_time() == second.run_to_full_time()
    assert first.state == second.state


def test_match_completes_when_all_cognitive_calls_fail() -> None:
    team_a = make_team("Team A", 78)
    team_b = make_team("Team B", 76)
    team_a_failure = FailingCompletion()
    team_b_failure = FailingCompletion()
    team_a_cognitive = make_cognitive(team_a.footballers[0].name, team_a_failure)
    team_b_cognitive = make_cognitive(team_b.footballers[0].name, team_b_failure)
    controller = MatchController(
        team_a,
        team_b,
        decision_makers(team_a_cognitive),
        decision_makers(team_b_cognitive),
        seed=303,
        team_a_coach=CoachAgent(team_a.name, api_key="", model=""),
        team_b_coach=CoachAgent(team_b.name, api_key="", model=""),
    )

    blocks = controller.run_to_full_time()

    assert controller.phase is MatchPhase.FULL_TIME
    assert len(blocks) == 4
    assert team_a_failure.call_count == 4
    assert team_b_failure.call_count == 4
    assert team_a_cognitive.last_used_fallback is True
    assert team_b_cognitive.last_used_fallback is True
