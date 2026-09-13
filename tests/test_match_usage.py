import json
from decimal import Decimal
from types import SimpleNamespace

from app.agents.coach import CoachAgent
from app.domain.enums import FootballerBehavior, MatchPhase, TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.footballers.cognitive import CognitiveFootballer
from app.footballers.reactive import ReactiveFootballer
from app.footballers.tactical import TacticalFootballer
from app.match.match_controller import MatchController
from app.usage.models import AgentType

PRICED_MODEL = "qwen/qwen3.8-27b"


class UsageCompletion:
    def __init__(
        self,
        field: str,
        value: str,
        *,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int,
    ) -> None:
        self.field = field
        self.value = value
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cached_tokens = cached_tokens

    def __call__(self, **_):
        return SimpleNamespace(
            id="usage-response",
            model=PRICED_MODEL,
            usage=SimpleNamespace(
                prompt_tokens=self.input_tokens,
                completion_tokens=self.output_tokens,
                total_tokens=self.input_tokens + self.output_tokens,
                prompt_tokens_details=SimpleNamespace(
                    cached_tokens=self.cached_tokens
                ),
            ),
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


def make_controller(seed: int) -> MatchController:
    team_a = make_team("AI United", 78)
    team_b = make_team("Neural FC", 76)
    team_a_cognitive = CognitiveFootballer(
        team_a.footballers[0].name,
        model=PRICED_MODEL,
        completion_create=UsageCompletion(
            "behavior",
            FootballerBehavior.SUPPORT.value,
            input_tokens=12,
            output_tokens=4,
            cached_tokens=3,
        ),
    )
    team_b_cognitive = CognitiveFootballer(
        team_b.footballers[0].name,
        model=PRICED_MODEL,
        completion_create=UsageCompletion(
            "behavior",
            FootballerBehavior.SUPPORT.value,
            input_tokens=12,
            output_tokens=4,
            cached_tokens=3,
        ),
    )
    team_a_makers = [
        team_a_cognitive,
        *[TacticalFootballer() for _ in range(3)],
        *[ReactiveFootballer() for _ in range(7)],
    ]
    team_b_makers = [
        team_b_cognitive,
        *[TacticalFootballer() for _ in range(3)],
        *[ReactiveFootballer() for _ in range(7)],
    ]
    return MatchController(
        team_a,
        team_b,
        team_a_makers,
        team_b_makers,
        seed=seed,
        team_a_coach=CoachAgent(
            team_a.name,
            model=PRICED_MODEL,
            completion_create=UsageCompletion(
                "tactic",
                TeamTactic.BALANCED.value,
                input_tokens=10,
                output_tokens=5,
                cached_tokens=2,
            ),
        ),
        team_b_coach=CoachAgent(
            team_b.name,
            model=PRICED_MODEL,
            completion_create=UsageCompletion(
                "tactic",
                TeamTactic.BALANCED.value,
                input_tokens=10,
                output_tokens=5,
                cached_tokens=2,
            ),
        ),
    )


def make_no_groq_controller(seed: int) -> MatchController:
    team_a = make_team("AI United", 78)
    team_b = make_team("Neural FC", 76)
    team_a_cognitive = CognitiveFootballer(
        team_a.footballers[0].name, api_key="", model=""
    )
    team_b_cognitive = CognitiveFootballer(
        team_b.footballers[0].name, api_key="", model=""
    )
    return MatchController(
        team_a,
        team_b,
        [team_a_cognitive, *[ReactiveFootballer() for _ in range(10)]],
        [team_b_cognitive, *[ReactiveFootballer() for _ in range(10)]],
        seed=seed,
        team_a_coach=CoachAgent(team_a.name, api_key="", model=""),
        team_b_coach=CoachAgent(team_b.name, api_key="", model=""),
    )


def test_successful_match_aggregates_coach_and_cognitive_usage() -> None:
    controller = make_controller(seed=400)

    controller.run_to_full_time()
    totals = controller.usage_tracker.match_totals()

    assert controller.phase is MatchPhase.FULL_TIME
    assert totals.calls == 16
    assert totals.input_tokens == 176
    assert totals.output_tokens == 72
    assert totals.total_tokens == 248
    assert totals.cached_tokens == 40
    assert totals.estimated_cost == Decimal("0.0004288")


def test_usage_is_available_by_agent_and_agent_type() -> None:
    controller = make_controller(seed=401)
    controller.run_to_full_time()

    coach = controller.usage_tracker.totals_for_agent("coach:ai-united")
    footballer = controller.usage_tracker.totals_for_agent(
        "footballer:ai-united-footballer-1"
    )
    coach_type = controller.usage_tracker.totals_for_agent_type(AgentType.COACH)
    cognitive_type = controller.usage_tracker.totals_for_agent_type(
        AgentType.COGNITIVE_FOOTBALLER
    )

    assert coach.calls == 4
    assert coach.total_tokens == 60
    assert footballer.calls == 4
    assert footballer.total_tokens == 64
    assert coach_type.calls == 8
    assert cognitive_type.calls == 8


def test_full_no_groq_match_has_zero_usage() -> None:
    controller = make_no_groq_controller(seed=402)

    controller.run_to_full_time()
    totals = controller.usage_tracker.match_totals()

    assert controller.phase is MatchPhase.FULL_TIME
    assert totals.calls == 0
    assert totals.input_tokens == 0
    assert totals.output_tokens == 0
    assert totals.total_tokens == 0
    assert totals.cached_tokens == 0
    assert totals.estimated_cost == Decimal("0")


def test_usage_tracking_does_not_change_seeded_match_result() -> None:
    first = make_controller(seed=403)
    second = make_controller(seed=403)

    first_blocks = first.run_to_full_time()
    second_blocks = second.run_to_full_time()

    assert first_blocks == second_blocks
    assert first.state == second.state
