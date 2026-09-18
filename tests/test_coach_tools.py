import json
from types import SimpleNamespace

import pytest

from app.agents.assistant import AssistantCoach
from app.agents.coach import CoachAgent
from app.agents.coach_context import CoachContext
from app.agents.coach_tools import COACH_TOOL_SCHEMAS, execute_coach_tool
from app.domain.enums import MatchPhase, TeamTactic
from app.domain.match_state import MatchState
from app.usage.models import AgentType
from app.web.session import WebMatchSession


def make_state() -> MatchState:
    return MatchState(
        minute=70,
        team_a_score=2,
        team_b_score=1,
        team_a_tactic=TeamTactic.ATTACK,
        team_b_tactic=TeamTactic.DEFEND,
        team_a_strength=80,
        team_b_strength=75,
        team_a_average_energy=72.5,
        team_b_average_energy=61.0,
    )


def make_context(*, is_team_a: bool = True) -> CoachContext:
    return CoachContext.from_match_state(
        make_state(),
        is_team_a=is_team_a,
        phase=MatchPhase.THIRD_BLOCK,
    )


def tool_call(name: str, arguments: str = "{}") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"call-{name}",
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def provider_response(
    *,
    content: str | None,
    tool_calls: list[SimpleNamespace] | None = None,
    response_id: str = "response",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=response_id,
        model="test-model",
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=tool_calls)
            )
        ],
    )


class ToolThenDecision:
    def __init__(self, tactic: TeamTactic) -> None:
        self.tactic = tactic
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return provider_response(
                content=None,
                tool_calls=[tool_call("get_score"), tool_call("get_team_energy")],
                response_id="tool-response",
            )
        return provider_response(
            content=json.dumps(
                {"tactic": self.tactic.value, "reason": "Use the match state."}
            ),
            response_id="decision-response",
        )


def test_tool_schemas_define_only_five_parameterless_read_only_lookups() -> None:
    assert {schema["function"]["name"] for schema in COACH_TOOL_SCHEMAS} == {
        "get_score",
        "get_match_phase",
        "get_team_energy",
        "get_opponent_energy",
        "get_current_tactic",
    }
    for schema in COACH_TOOL_SCHEMAS:
        parameters = schema["function"]["parameters"]
        assert schema["type"] == "function"
        assert parameters == {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }


@pytest.mark.parametrize(
    ("is_team_a", "expected"),
    [
        (
            True,
            {
                "get_score": {"team_score": 2, "opponent_score": 1},
                "get_match_phase": {"match_phase": MatchPhase.THIRD_BLOCK.value},
                "get_team_energy": {"team_energy": 72.5},
                "get_opponent_energy": {"opponent_energy": 61.0},
                "get_current_tactic": {"current_tactic": "ATTACK"},
            },
        ),
        (
            False,
            {
                "get_score": {"team_score": 1, "opponent_score": 2},
                "get_match_phase": {"match_phase": MatchPhase.THIRD_BLOCK.value},
                "get_team_energy": {"team_energy": 61.0},
                "get_opponent_energy": {"opponent_energy": 72.5},
                "get_current_tactic": {"current_tactic": "DEFEND"},
            },
        ),
    ],
)
def test_tools_return_perspective_aware_values_for_both_team_selections(
    is_team_a: bool,
    expected: dict[str, dict],
) -> None:
    context = make_context(is_team_a=is_team_a)

    actual = {
        name: json.loads(execute_coach_tool(name, "{}", context))
        for name in expected
    }

    assert actual == expected


def test_tool_execution_cannot_mutate_match_state_or_context() -> None:
    state = make_state()
    context = CoachContext.from_match_state(
        state,
        is_team_a=True,
        phase=MatchPhase.THIRD_BLOCK,
    )
    state_before = state.model_copy(deep=True)
    context_before = context.model_copy(deep=True)

    for schema in COACH_TOOL_SCHEMAS:
        execute_coach_tool(schema["function"]["name"], "{}", context)

    assert state == state_before
    assert context == context_before


@pytest.mark.parametrize(
    ("agent_type", "method_name", "expected_tactic"),
    [
        (AssistantCoach, "recommend_tactic", TeamTactic.DEFEND),
        (CoachAgent, "choose_tactic", TeamTactic.ATTACK),
    ],
)
def test_agents_can_call_tools_before_returning_a_validated_decision(
    agent_type,
    method_name: str,
    expected_tactic: TeamTactic,
) -> None:
    completion = ToolThenDecision(expected_tactic)
    agent = agent_type(
        "Test FC",
        model="test-model",
        completion_create=completion,
    )

    decision = getattr(agent, method_name)(make_context())

    assert decision.tactic is expected_tactic
    assert agent.provider_call_count == 2
    assert completion.calls[0]["tool_choice"] == "auto"
    assert "response_format" not in completion.calls[0]
    assert "tools" not in completion.calls[1]
    assert "tool_choice" not in completion.calls[1]
    assert completion.calls[1]["response_format"] == {"type": "json_object"}
    assert completion.calls[0]["reasoning_format"] == "hidden"
    assert completion.calls[1]["reasoning_format"] == "hidden"
    assert "team_score" not in completion.calls[0]["messages"][1]["content"]
    tool_messages = [
        message
        for message in completion.calls[1]["messages"]
        if message["role"] == "tool"
    ]
    assert json.loads(tool_messages[0]["content"]) == {
        "team_score": 2,
        "opponent_score": 1,
    }
    assert json.loads(tool_messages[1]["content"]) == {"team_energy": 72.5}


@pytest.mark.parametrize(
    "requested_tool",
    [tool_call("change_score"), tool_call("get_score", "not-json")],
)
def test_unknown_or_malformed_tool_call_falls_back_safely(
    requested_tool: SimpleNamespace,
) -> None:
    agent = CoachAgent(
        "Test FC",
        model="test-model",
        completion_create=lambda **_: provider_response(
            content=None,
            tool_calls=[requested_tool],
        ),
    )

    decision = agent.choose_tactic(make_context())

    assert decision.tactic is TeamTactic.ATTACK
    assert agent.last_used_fallback is True
    assert agent.last_error == "tool_execution_failed"
    assert agent.last_error_category == "TOOL_EXECUTION"


def test_invalid_final_decision_after_groq_tools_is_rejected() -> None:
    calls = 0

    def completion_create(**_):
        nonlocal calls
        calls += 1
        if calls == 1:
            return provider_response(
                content=None,
                tool_calls=[tool_call("get_score")],
            )
        return provider_response(
            content='{"tactic":"PRESS","reason":"Invalid tactic."}',
        )

    agent = CoachAgent(
        "Test FC",
        model="test-model",
        completion_create=completion_create,
        gemini_api_key="",
        gemini_model="",
    )

    decision = agent.choose_tactic(make_context())

    assert decision.tactic is TeamTactic.ATTACK
    assert agent.last_used_fallback is True
    assert agent.last_error_category == "MALFORMED_RESPONSE"


def test_assistant_tool_round_trip_tracks_both_provider_calls() -> None:
    completion = ToolThenDecision(TeamTactic.DEFEND)
    assistant = AssistantCoach(
        "AI United",
        model="test-model",
        completion_create=completion,
    )
    session = WebMatchSession(seed=81, api_key="", model="")

    recommendation = session.controller.request_assistant_recommendation(
        assistant,
        is_team_a=True,
        phase=MatchPhase.FIRST_BLOCK,
    )
    totals = session.controller.usage_tracker.totals_for_agent_type(
        AgentType.ASSISTANT_COACH
    )

    assert recommendation.tactic is TeamTactic.DEFEND
    assert session.controller.state.team_a_tactic is TeamTactic.BALANCED
    assert totals.calls == 2
    assert totals.input_tokens == 20
    assert totals.output_tokens == 10
    assert totals.total_tokens == 30
