import json
import logging
from types import SimpleNamespace

from app.agents.assistant import AssistantCoach
from app.agents.coach import CoachAgent
from app.agents.coach_context import CoachContext
from app.domain.enums import MatchPhase, TeamTactic
from app.domain.match_state import MatchState
from app.usage.models import AgentType, ProviderName
from app.web.session import WebMatchSession


def context() -> CoachContext:
    return CoachContext.from_match_state(
        MatchState(
            minute=70,
            team_a_score=2,
            team_b_score=1,
            team_a_tactic=TeamTactic.ATTACK,
            team_b_tactic=TeamTactic.DEFEND,
            team_a_strength=80,
            team_b_strength=75,
            team_a_average_energy=72.5,
            team_b_average_energy=61,
        ),
        is_team_a=True,
        phase=MatchPhase.THIRD_BLOCK,
    )


def groq_response(tactic: str = "BALANCED") -> SimpleNamespace:
    return SimpleNamespace(
        id="groq-response",
        model="groq-test-model",
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=4,
            total_tokens=14,
        ),
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {"tactic": tactic, "reason": "Groq decision."}
                    ),
                    tool_calls=None,
                )
            )
        ],
    )


def gemini_response(
    *,
    tactic: str | None = "BALANCED",
    function_calls: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    text = (
        json.dumps({"tactic": tactic, "reason": "Gemini decision."})
        if tactic is not None
        else None
    )
    return SimpleNamespace(
        response_id="gemini-response",
        model_version="gemini-3.1-flash-lite",
        text=text,
        function_calls=function_calls,
        usage_metadata=SimpleNamespace(
            prompt_token_count=7,
            candidates_token_count=3,
            total_token_count=10,
            cached_content_token_count=1,
        ),
        candidates=[
            SimpleNamespace(content=SimpleNamespace(role="model", parts=[]))
        ],
    )


class GeminiToolThenDecision:
    def __init__(self, tactic: str = "DEFEND") -> None:
        self.tactic = tactic
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return gemini_response(
                tactic=None,
                function_calls=[
                    SimpleNamespace(name="get_score", args={}),
                    SimpleNamespace(name="get_team_energy", args={}),
                ],
            )
        return gemini_response(tactic=self.tactic, function_calls=None)


def configured_agent(groq, gemini) -> CoachAgent:
    return CoachAgent(
        "Test FC",
        model="groq-test-model",
        completion_create=groq,
        gemini_model="gemini-3.1-flash-lite",
        gemini_generate_content=gemini,
    )


def test_groq_success_never_invokes_gemini() -> None:
    gemini_calls = []
    agent = configured_agent(
        lambda **_: groq_response("ATTACK"),
        lambda **kwargs: gemini_calls.append(kwargs),
    )

    decision = agent.choose_tactic(context())

    assert decision.tactic is TeamTactic.ATTACK
    assert gemini_calls == []
    assert agent.last_successful_provider is ProviderName.GROQ


def test_groq_failure_invokes_gemini_and_avoids_deterministic_fallback() -> None:
    def groq_failure(**_):
        raise RuntimeError("Groq unavailable")

    gemini_calls = []

    def gemini_success(**kwargs):
        gemini_calls.append(kwargs)
        return gemini_response(tactic="DEFEND")

    agent = configured_agent(groq_failure, gemini_success)

    decision = agent.choose_tactic(context())

    assert decision.tactic is TeamTactic.DEFEND
    assert len(gemini_calls) == 1
    assert agent.last_successful_provider is ProviderName.GEMINI
    assert agent.last_used_fallback is False


def test_runtime_status_shows_gemini_when_it_returns_the_valid_decision() -> None:
    def groq_failure(**_):
        raise RuntimeError("Groq unavailable")

    agent = configured_agent(
        groq_failure,
        lambda **_: gemini_response(tactic="DEFEND"),
    )
    agent.choose_tactic(context())
    session = WebMatchSession(seed=103, api_key="", model="")
    session._latest_ai_agent = agent

    assert session.state_payload()["provider_status"] == {
        "provider": "GEMINI",
        "state": "ACTIVE",
    }


def test_invalid_groq_contract_invokes_gemini() -> None:
    agent = configured_agent(
        lambda **_: groq_response("PRESS"),
        lambda **_: gemini_response(tactic="BALANCED"),
    )

    decision = agent.choose_tactic(context())

    assert decision.tactic is TeamTactic.BALANCED
    assert agent.last_successful_provider is ProviderName.GEMINI
    assert agent.last_used_fallback is False


def test_both_providers_failing_uses_deterministic_fallback() -> None:
    def fail(**_):
        raise RuntimeError("provider unavailable")

    agent = configured_agent(fail, fail)

    decision = agent.choose_tactic(context())

    assert decision.tactic is TeamTactic.ATTACK
    assert decision.reason == "fallback_provider_error"
    assert agent.last_used_fallback is True
    assert agent.last_successful_provider is None


def test_groq_failure_without_gemini_uses_deterministic_fallback() -> None:
    def groq_failure(**_):
        raise RuntimeError("Groq unavailable")

    agent = CoachAgent(
        "Test FC",
        model="groq-test-model",
        completion_create=groq_failure,
        gemini_api_key="",
    )

    decision = agent.choose_tactic(context())

    assert agent.is_groq_configured is True
    assert agent.is_gemini_configured is False
    assert decision.tactic is TeamTactic.ATTACK
    assert agent.last_used_fallback is True
    assert agent.last_successful_provider is None


def test_runtime_status_shows_deterministic_fallback_without_error_detail() -> None:
    sensitive = "private provider diagnostic"

    def fail(**_):
        raise RuntimeError(sensitive)

    agent = configured_agent(fail, fail)
    agent.choose_tactic(context())
    session = WebMatchSession(seed=104, api_key="", model="")
    session._latest_ai_agent = agent

    payload = session.state_payload()

    assert payload["provider_status"] == {
        "provider": "FALLBACK",
        "state": "DETERMINISTIC",
    }
    assert sensitive not in json.dumps(payload)


def test_gemini_tool_round_trip_is_read_only_and_structured() -> None:
    completion = GeminiToolThenDecision()

    def groq_failure(**_):
        raise RuntimeError("Groq unavailable")

    agent = configured_agent(groq_failure, completion)
    decision_context = context()
    before = decision_context.model_copy(deep=True)

    decision = agent.choose_tactic(decision_context)

    assert decision.tactic is TeamTactic.DEFEND
    assert decision_context == before
    assert len(completion.calls) == 2
    first_config = completion.calls[0]["config"]
    final_config = completion.calls[1]["config"]
    assert len(first_config.tools[0].function_declarations) == 5
    assert first_config.automatic_function_calling.disable is True
    assert first_config.response_mime_type is None
    assert final_config.tools is None
    assert final_config.response_mime_type == "application/json"


def test_gemini_final_response_still_requires_pydantic_contract() -> None:
    def groq_failure(**_):
        raise RuntimeError("Groq unavailable")

    agent = configured_agent(
        groq_failure,
        lambda **_: SimpleNamespace(
            response_id="bad-gemini",
            model_version="gemini-3.1-flash-lite",
            text='{"tactic":"PRESS","reason":"Invalid."}',
            function_calls=None,
            usage_metadata=None,
        ),
    )

    decision = agent.choose_tactic(context())

    assert decision.tactic is TeamTactic.ATTACK
    assert agent.last_used_fallback is True
    assert agent.last_error_category == "MALFORMED_RESPONSE"


def test_assistant_gemini_recommendation_cannot_mutate_human_tactic() -> None:
    assistant = AssistantCoach(
        "AI United",
        api_key="",
        model="",
        gemini_model="gemini-3.1-flash-lite",
        gemini_generate_content=lambda **_: gemini_response(tactic="DEFEND"),
    )
    session = WebMatchSession(
        seed=101,
        api_key="",
        model="",
        gemini_api_key="",
        gemini_model="",
    )

    recommendation = session.controller.request_assistant_recommendation(
        assistant,
        is_team_a=True,
        phase=MatchPhase.FIRST_BLOCK,
    )

    assert recommendation.tactic is TeamTactic.DEFEND
    assert session.controller.state.team_a_tactic is TeamTactic.BALANCED


def test_usage_tracking_distinguishes_failed_groq_and_successful_gemini() -> None:
    def groq_failure(**_):
        raise RuntimeError("Groq unavailable")

    assistant = AssistantCoach(
        "AI United",
        model="groq-test-model",
        completion_create=groq_failure,
        gemini_model="gemini-3.1-flash-lite",
        gemini_generate_content=lambda **_: gemini_response(tactic="BALANCED"),
    )
    session = WebMatchSession(
        seed=102,
        api_key="",
        model="",
        gemini_api_key="",
        gemini_model="",
    )

    session.controller.request_assistant_recommendation(
        assistant,
        is_team_a=True,
        phase=MatchPhase.FIRST_BLOCK,
    )
    records = session.controller.usage_tracker.records

    assert [record.provider for record in records] == [
        ProviderName.GROQ,
        ProviderName.GEMINI,
    ]
    assert records[0].total_tokens is None
    assert records[1].total_tokens == 10
    assert (
        session.controller.usage_tracker.totals_for_agent_type(
            AgentType.ASSISTANT_COACH
        ).calls
        == 2
    )


def test_provider_logs_redact_keys_and_omit_raw_sensitive_content(caplog) -> None:
    groq_key = "gsk_private-key"
    gemini_key = "gemini-private-key"
    sensitive = "private match request payload"

    def groq_failure(**_):
        raise RuntimeError(f"{groq_key} {sensitive}")

    def gemini_failure(**_):
        raise RuntimeError(f"{gemini_key} {sensitive}")

    agent = CoachAgent(
        "Test FC",
        api_key=groq_key,
        model="groq-test-model",
        completion_create=groq_failure,
        gemini_api_key=gemini_key,
        gemini_model="gemini-3.1-flash-lite",
        gemini_generate_content=gemini_failure,
    )

    with caplog.at_level(logging.ERROR):
        agent.choose_tactic(context())

    assert groq_key not in caplog.text
    assert gemini_key not in caplog.text
    assert sensitive not in caplog.text
