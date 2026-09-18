import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agents.coach import CoachAgent, CoachDecision
from app.agents.coach_context import CoachContext, MatchSituation
from app.domain.enums import BlockAdvantage, MatchPhase, TeamTactic
from app.domain.match_state import MatchState
from app.footballers.context import PreviousBlockResult


def make_state(
    *,
    team_a_score: int = 0,
    team_b_score: int = 0,
    previous_block_result: str | None = None,
) -> MatchState:
    return MatchState(
        minute=25,
        team_a_score=team_a_score,
        team_b_score=team_b_score,
        team_a_tactic=TeamTactic.ATTACK,
        team_b_tactic=TeamTactic.DEFEND,
        team_a_strength=80,
        team_b_strength=75,
        team_a_average_energy=85,
        team_b_average_energy=82,
        previous_block_result=previous_block_result,
    )


def make_context(tactic: TeamTactic = TeamTactic.BALANCED) -> CoachContext:
    return CoachContext(
        phase=MatchPhase.FIRST_BLOCK,
        team_score=0,
        opponent_score=0,
        situation=MatchSituation.DRAWING,
        current_tactic=tactic,
        team_average_energy=100,
        opponent_average_energy=100,
        team_strength=75,
        opponent_strength=75,
    )


def response_with(content: str):
    return SimpleNamespace(
        id="response-1",
        model="test-model",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


def configured_agent(completion_create) -> CoachAgent:
    return CoachAgent(
        "Test FC",
        api_key="test-key",
        model="test-model",
        completion_create=completion_create,
    )


def test_context_contains_only_approved_information() -> None:
    assert set(CoachContext.model_fields) == {
        "phase",
        "team_score",
        "opponent_score",
        "situation",
        "current_tactic",
        "team_average_energy",
        "opponent_average_energy",
        "team_strength",
        "opponent_strength",
        "previous_block_result",
    }


@pytest.mark.parametrize(
    ("team_a_score", "team_b_score", "expected"),
    [
        (2, 1, MatchSituation.WINNING),
        (1, 1, MatchSituation.DRAWING),
        (0, 1, MatchSituation.LOSING),
    ],
)
def test_context_calculates_match_situation(
    team_a_score: int,
    team_b_score: int,
    expected: MatchSituation,
) -> None:
    context = CoachContext.from_match_state(
        make_state(team_a_score=team_a_score, team_b_score=team_b_score),
        is_team_a=True,
        phase=MatchPhase.SECOND_BLOCK,
    )

    assert context.situation is expected


def test_context_represents_previous_result_from_each_team_perspective() -> None:
    state = make_state(
        previous_block_result=BlockAdvantage.TEAM_A_ADVANTAGE.value
    )

    team_a_context = CoachContext.from_match_state(
        state, is_team_a=True, phase=MatchPhase.SECOND_BLOCK
    )
    team_b_context = CoachContext.from_match_state(
        state, is_team_a=False, phase=MatchPhase.SECOND_BLOCK
    )

    assert team_a_context.previous_block_result is PreviousBlockResult.POSITIVE
    assert team_b_context.previous_block_result is PreviousBlockResult.NEGATIVE


def test_unknown_previous_result_is_not_treated_as_negative() -> None:
    context = CoachContext.from_match_state(
        make_state(previous_block_result="UNKNOWN"),
        is_team_a=True,
        phase=MatchPhase.SECOND_BLOCK,
    )

    assert context.previous_block_result is None


@pytest.mark.parametrize("tactic", list(TeamTactic))
def test_valid_structured_tactic_is_accepted(tactic: TeamTactic) -> None:
    calls = []

    def completion_create(**kwargs):
        calls.append(kwargs)
        return response_with(
            json.dumps({"tactic": tactic.value, "reason": "Brief tactical reason."})
        )

    agent = configured_agent(completion_create)

    decision = agent.choose_tactic(make_context())

    assert decision.tactic is tactic
    assert decision.reason == "Brief tactical reason."
    assert agent.provider_call_count == 1
    assert "response_format" not in calls[0]
    assert calls[0]["tool_choice"] == "auto"
    assert calls[0]["reasoning_format"] == "hidden"
    assert "valid JSON object only" in calls[0]["messages"][0]["content"]


def test_invalid_tactic_is_rejected_by_response_model() -> None:
    with pytest.raises(ValidationError):
        CoachDecision(tactic="PRESS", reason="Invalid tactic")


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"tactic":"PRESS","reason":"Invalid"}',
        '{"tactic":"ATTACK"}',
        '{"tactic":"ATTACK","reason":"Invalid extra field","goal":true}',
    ],
)
def test_malformed_or_invalid_output_retains_current_tactic(content: str) -> None:
    agent = configured_agent(lambda **_: response_with(content))

    decision = agent.choose_tactic(make_context(TeamTactic.DEFEND))

    assert decision.tactic is TeamTactic.DEFEND
    assert agent.last_error == "invalid_response"


def test_missing_configuration_uses_fallback_without_provider_call() -> None:
    agent = CoachAgent("Test FC", api_key="", model="")

    decision = agent.choose_tactic(make_context(TeamTactic.ATTACK))

    assert decision.tactic is TeamTactic.ATTACK
    assert agent.provider_call_count == 0
    assert agent.last_error == "missing_configuration"


def test_provider_failure_retains_current_tactic() -> None:
    def failing_completion(**_):
        raise RuntimeError("sensitive provider detail")

    agent = configured_agent(failing_completion)

    decision = agent.choose_tactic(make_context(TeamTactic.BALANCED))

    assert decision.tactic is TeamTactic.BALANCED
    assert agent.last_error == "provider_error"
    assert "sensitive" not in decision.reason


def test_response_metadata_is_preserved_without_aggregation() -> None:
    agent = configured_agent(
        lambda **_: response_with('{"tactic":"ATTACK","reason":"Push forward."}')
    )

    agent.choose_tactic(make_context())

    assert len(agent.response_metadata) == 1
    assert agent.response_metadata[0].response_id == "response-1"
    assert agent.response_metadata[0].provider.value == "GROQ"
    assert agent.response_metadata[0].model == "test-model"
    assert agent.response_metadata[0].usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
