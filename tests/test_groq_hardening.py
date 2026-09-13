import logging
from types import SimpleNamespace

import pytest

from app.agents.coach import CoachAgent
from app.agents.coach_context import CoachContext, MatchSituation
from app.agents.groq_support import provider_error_details
from app.domain.enums import MatchPhase, TeamTactic


class FakeProviderError(Exception):
    def __init__(self, status_code: int, error_type: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = {"error": {"type": error_type, "message": message}}


def make_context() -> CoachContext:
    return CoachContext(
        phase=MatchPhase.FIRST_BLOCK,
        team_score=0,
        opponent_score=0,
        situation=MatchSituation.DRAWING,
        current_tactic=TeamTactic.BALANCED,
        team_average_energy=100,
        opponent_average_energy=100,
        team_strength=75,
        opponent_strength=75,
    )


@pytest.mark.parametrize(
    ("status", "error_type", "category"),
    [
        (400, "invalid_request_error", "INVALID_REQUEST"),
        (401, "authentication_error", "AUTHENTICATION"),
        (429, "rate_limit_error", "RATE_LIMIT"),
        (503, "server_error", "PROVIDER_ERROR"),
    ],
)
def test_provider_errors_are_categorized(
    status: int,
    error_type: str,
    category: str,
) -> None:
    details = provider_error_details(
        FakeProviderError(status, error_type, "provider rejected request")
    )

    assert details.status == status
    assert details.error_type == error_type
    assert details.category == category


def test_provider_log_is_actionable_and_sanitized(caplog) -> None:
    secret = "gsk_secret-value-123"

    def fail(**_):
        raise FakeProviderError(
            400,
            "invalid_request_error",
            f"invalid format; Authorization: Bearer {secret}",
        )

    agent = CoachAgent(
        "Test FC",
        api_key=secret,
        model="qwen/qwen3.8-27b",
        completion_create=fail,
    )

    with caplog.at_level(logging.ERROR, logger="ai_football_agentic.groq"):
        agent.choose_tactic(make_context())

    assert "agent=coach:test-fc" in caplog.text
    assert "model=qwen/qwen3.8-27b" in caplog.text
    assert "status=400" in caplog.text
    assert "category=INVALID_REQUEST" in caplog.text
    assert "fallback=deterministic" in caplog.text
    assert secret not in caplog.text
    assert "gsk_" not in caplog.text


def test_success_after_failure_clears_error_state() -> None:
    outcomes = iter(
        [
            FakeProviderError(503, "server_error", "temporary outage"),
            SimpleNamespace(
                id="response-2",
                model="qwen/qwen3.8-27b",
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"tactic":"ATTACK","reason":"Push now."}'
                        )
                    )
                ],
            ),
        ]
    )

    def completion_create(**_):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    agent = CoachAgent(
        "Test FC",
        api_key="test-key",
        model="qwen/qwen3.8-27b",
        completion_create=completion_create,
    )

    agent.choose_tactic(make_context())
    assert agent.last_provider_succeeded is False
    assert agent.last_error_category == "PROVIDER_ERROR"

    decision = agent.choose_tactic(make_context())

    assert decision.tactic is TeamTactic.ATTACK
    assert agent.last_provider_succeeded is True
    assert agent.last_error is None
    assert agent.last_error_category is None
