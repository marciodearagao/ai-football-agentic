import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.domain.enums import (
    FootballerBehavior,
    MatchPhase,
    MatchSituation,
    TeamTactic,
)
from app.domain.footballer import Footballer
from app.footballers.cognitive import CognitiveDecision, CognitiveFootballer
from app.footballers.cognitive_context import CognitiveFootballerContext
from app.footballers.context import PreviousBlockResult


def make_footballer(energy: float = 80) -> Footballer:
    return Footballer(
        name="Alex Morgan",
        skill=82,
        intelligence=88,
        stamina=84,
        energy=energy,
    )


def make_context(
    footballer: Footballer,
    *,
    score_difference: int = 0,
    tactic: TeamTactic = TeamTactic.BALANCED,
    previous_block_result: PreviousBlockResult | None = None,
) -> CognitiveFootballerContext:
    return CognitiveFootballerContext.for_footballer(
        footballer,
        phase=MatchPhase.SECOND_BLOCK,
        score_difference=score_difference,
        team_tactic=tactic,
        team_average_energy=78,
        opponent_average_energy=75,
        previous_block_result=previous_block_result,
    )


def response_with(content: str):
    return SimpleNamespace(
        id="cognitive-response-1",
        model="test-model",
        usage={"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


def configured_footballer(completion_create) -> CognitiveFootballer:
    return CognitiveFootballer(
        "Alex Morgan",
        api_key="test-key",
        model="test-model",
        completion_create=completion_create,
    )


def test_context_contains_only_approved_fields() -> None:
    assert set(CognitiveFootballerContext.model_fields) == {
        "phase",
        "score_difference",
        "situation",
        "footballer_energy",
        "footballer_skill",
        "footballer_stamina",
        "footballer_intelligence",
        "team_tactic",
        "team_average_energy",
        "opponent_average_energy",
        "previous_block_result",
    }


def test_context_includes_footballer_energy_and_team_tactic() -> None:
    footballer = make_footballer(energy=63)

    context = make_context(footballer, tactic=TeamTactic.DEFEND)

    assert context.footballer_energy == 63
    assert context.team_tactic is TeamTactic.DEFEND


@pytest.mark.parametrize(
    ("score_difference", "expected"),
    [
        (1, MatchSituation.WINNING),
        (0, MatchSituation.DRAWING),
        (-1, MatchSituation.LOSING),
    ],
)
def test_context_calculates_score_situation(
    score_difference: int,
    expected: MatchSituation,
) -> None:
    context = make_context(
        make_footballer(),
        score_difference=score_difference,
    )

    assert context.situation is expected


def test_context_preserves_normalized_previous_block_result() -> None:
    context = make_context(
        make_footballer(),
        previous_block_result=PreviousBlockResult.NEGATIVE,
    )

    assert context.previous_block_result is PreviousBlockResult.NEGATIVE


@pytest.mark.parametrize("behavior", list(FootballerBehavior))
def test_valid_structured_behavior_is_accepted(
    behavior: FootballerBehavior,
) -> None:
    calls = []

    def completion_create(**kwargs):
        calls.append(kwargs)
        return response_with(
            json.dumps(
                {"behavior": behavior.value, "reason": "Brief behavior reason."}
            )
        )

    cognitive = configured_footballer(completion_create)

    result = cognitive.choose_behavior(
        make_footballer(),
        make_context(make_footballer()),
    )

    assert result is behavior
    assert cognitive.last_used_fallback is False
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert calls[0]["reasoning_format"] == "hidden"
    assert "valid JSON object only" in calls[0]["messages"][0]["content"]


def test_unsupported_behavior_is_rejected_by_response_model() -> None:
    with pytest.raises(ValidationError):
        CognitiveDecision(behavior="SHOOT", reason="Invalid behavior")


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"behavior":"SHOOT","reason":"Invalid"}',
        '{"behavior":"ATTACK"}',
        '{"behavior":"ATTACK","reason":"Invalid extra","goal":true}',
    ],
)
def test_malformed_response_uses_tactical_fallback(content: str) -> None:
    footballer = make_footballer(energy=80)
    cognitive = configured_footballer(lambda **_: response_with(content))

    result = cognitive.choose_behavior(
        footballer,
        make_context(footballer, score_difference=-1),
    )

    assert result is FootballerBehavior.ATTACK
    assert cognitive.last_used_fallback is True
    assert cognitive.last_error == "invalid_response"


def test_missing_configuration_uses_tactical_fallback() -> None:
    footballer = make_footballer(energy=80)
    cognitive = CognitiveFootballer("Alex Morgan", api_key="", model="")

    result = cognitive.choose_behavior(
        footballer,
        make_context(footballer, tactic=TeamTactic.DEFEND),
    )

    assert result is FootballerBehavior.PRESS
    assert cognitive.provider_call_count == 0
    assert cognitive.last_error == "missing_configuration"


def test_provider_failure_uses_tactical_fallback() -> None:
    def failing_completion(**_):
        raise TimeoutError("sensitive provider detail")

    footballer = make_footballer(energy=34)
    cognitive = configured_footballer(failing_completion)

    result = cognitive.choose_behavior(footballer, make_context(footballer))

    assert result is FootballerBehavior.CONSERVE_ENERGY
    assert isinstance(result, FootballerBehavior)
    assert cognitive.last_error == "provider_error"


def test_response_metadata_is_preserved_without_usage_aggregation() -> None:
    footballer = make_footballer()
    cognitive = configured_footballer(
        lambda **_: response_with(
            '{"behavior":"SUPPORT","reason":"Keep the structure."}'
        )
    )

    cognitive.choose_behavior(footballer, make_context(footballer))

    assert len(cognitive.response_metadata) == 1
    assert cognitive.response_metadata[0].response_id == "cognitive-response-1"
    assert cognitive.response_metadata[0].model == "test-model"
    assert cognitive.response_metadata[0].usage == {
        "prompt_tokens": 12,
        "completion_tokens": 4,
        "total_tokens": 16,
    }
