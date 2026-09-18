from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.usage.models import AgentType, ProviderName, UsageRecord, make_agent_id
from app.usage.tracker import UsageTracker


def make_record(
    agent_id: str = "coach:ai-united",
    agent_type: AgentType = AgentType.COACH,
    *,
    input_tokens: int = 100,
    output_tokens: int = 20,
    cached_tokens: int | None = None,
    estimated_cost: Decimal | None = Decimal("0.0001"),
) -> UsageRecord:
    return UsageRecord(
        agent_id=agent_id,
        agent_type=agent_type,
        model="qwen/qwen3.8-27b",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cached_tokens=cached_tokens,
        estimated_cost=estimated_cost,
    )


def test_valid_usage_record_creation() -> None:
    record = make_record(cached_tokens=10)

    assert record.total_tokens == 120
    assert record.cached_tokens == 10
    assert record.used_fallback is False
    assert record.provider is ProviderName.GROQ


@pytest.mark.parametrize(
    "field",
    ["input_tokens", "output_tokens", "total_tokens", "cached_tokens"],
)
def test_token_values_cannot_be_negative(field: str) -> None:
    data = make_record().model_dump()
    data[field] = -1

    with pytest.raises(ValidationError):
        UsageRecord(**data)


def test_total_tokens_must_equal_input_plus_output() -> None:
    with pytest.raises(ValidationError):
        UsageRecord(
            agent_id="coach:ai-united",
            agent_type=AgentType.COACH,
            input_tokens=10,
            output_tokens=5,
            total_tokens=99,
        )


def test_cached_tokens_are_optional() -> None:
    assert make_record().cached_tokens is None


def test_agent_ids_are_simple_and_deterministic() -> None:
    assert make_agent_id(AgentType.ASSISTANT_COACH, "AI United") == "assistant:ai-united"
    assert make_agent_id(AgentType.COACH, "AI United") == "coach:ai-united"
    assert (
        make_agent_id(AgentType.COGNITIVE_FOOTBALLER, "AI United Player 1")
        == "footballer:ai-united-player-1"
    )


def test_one_record_increments_calls() -> None:
    tracker = UsageTracker()

    tracker.record(make_record())

    assert tracker.match_totals().calls == 1


def test_multiple_records_aggregate_match_totals() -> None:
    tracker = UsageTracker()
    tracker.record(make_record(cached_tokens=10))
    tracker.record(
        make_record(
            agent_id="footballer:player-1",
            agent_type=AgentType.COGNITIVE_FOOTBALLER,
            input_tokens=50,
            output_tokens=10,
            cached_tokens=5,
            estimated_cost=Decimal("0.00005"),
        )
    )

    totals = tracker.match_totals()

    assert totals.calls == 2
    assert totals.input_tokens == 150
    assert totals.output_tokens == 30
    assert totals.total_tokens == 180
    assert totals.cached_tokens == 15
    assert totals.estimated_cost == Decimal("0.00015")


def test_totals_by_agent_are_correct() -> None:
    tracker = UsageTracker()
    tracker.record(make_record())
    tracker.record(make_record())
    tracker.record(make_record(agent_id="coach:neural-fc"))

    totals = tracker.totals_for_agent("coach:ai-united")

    assert totals.calls == 2
    assert totals.total_tokens == 240


def test_totals_by_agent_type_are_correct() -> None:
    tracker = UsageTracker()
    tracker.record(make_record())
    tracker.record(
        make_record(
            agent_id="footballer:player-1",
            agent_type=AgentType.COGNITIVE_FOOTBALLER,
        )
    )

    coach_totals = tracker.totals_for_agent_type(AgentType.COACH)
    footballer_totals = tracker.totals_for_agent_type(
        AgentType.COGNITIVE_FOOTBALLER
    )

    assert coach_totals.calls == 1
    assert footballer_totals.calls == 1


def test_provider_metadata_is_normalized_from_sdk_style_object() -> None:
    tracker = UsageTracker()
    usage = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=20,
        total_tokens=120,
        prompt_tokens_details=SimpleNamespace(cached_tokens=15),
    )
    metadata = SimpleNamespace(model="qwen/qwen3.8-27b", usage=usage)

    record = tracker.record_provider_attempt(
        agent_id="coach:ai-united",
        agent_type=AgentType.COACH,
        model="fallback-model",
        used_fallback=False,
        response_metadata=metadata,
    )

    assert record.input_tokens == 100
    assert record.output_tokens == 20
    assert record.total_tokens == 120
    assert record.cached_tokens == 15
    assert record.estimated_cost == Decimal("0.00016")


def test_failed_provider_attempt_has_no_fabricated_tokens_or_cost() -> None:
    tracker = UsageTracker()

    record = tracker.record_provider_attempt(
        agent_id="coach:ai-united",
        agent_type=AgentType.COACH,
        model="qwen/qwen3.8-27b",
        used_fallback=True,
    )

    assert record.input_tokens is None
    assert record.output_tokens is None
    assert record.total_tokens is None
    assert record.estimated_cost is None
    assert tracker.match_totals().calls == 1
    assert tracker.match_totals().estimated_cost is None


def test_unknown_model_preserves_tokens_with_unavailable_cost() -> None:
    tracker = UsageTracker()

    record = tracker.record_provider_attempt(
        agent_id="coach:ai-united",
        agent_type=AgentType.COACH,
        model="unknown-model",
        used_fallback=False,
        response_metadata={
            "model": "unknown-model",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        },
    )

    assert record.total_tokens == 15
    assert record.estimated_cost is None


def test_malformed_provider_usage_does_not_break_tracking() -> None:
    tracker = UsageTracker()

    record = tracker.record_provider_attempt(
        agent_id="coach:ai-united",
        agent_type=AgentType.COACH,
        model="qwen/qwen3.8-27b",
        used_fallback=False,
        response_metadata={
            "usage": {
                "prompt_tokens": "invalid",
                "completion_tokens": 5,
                "total_tokens": 99,
                "cached_tokens": -1,
            }
        },
    )

    assert record.input_tokens is None
    assert record.output_tokens == 5
    assert record.total_tokens == 99
    assert record.cached_tokens is None
    assert record.estimated_cost is None


def test_gemini_usage_fields_and_provider_are_normalized() -> None:
    tracker = UsageTracker()

    record = tracker.record_provider_attempt(
        agent_id="coach:ai-united",
        agent_type=AgentType.COACH,
        provider=ProviderName.GEMINI,
        model="gemini-3.1-flash-lite",
        used_fallback=False,
        response_metadata={
            "provider": "GEMINI",
            "model": "gemini-3.1-flash-lite",
            "usage": {
                "prompt_token_count": 12,
                "candidates_token_count": 4,
                "total_token_count": 16,
                "cached_content_token_count": 2,
            },
        },
    )

    assert record.provider is ProviderName.GEMINI
    assert record.input_tokens == 12
    assert record.output_tokens == 4
    assert record.total_tokens == 16
    assert record.cached_tokens == 2
    assert record.estimated_cost is None
    assert tracker.totals_for_provider(ProviderName.GEMINI).calls == 1
