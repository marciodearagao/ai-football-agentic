import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from app.agents.groq_support import (
    JSON_RESPONSE_FORMAT,
    create_completion,
    log_malformed_response,
    log_provider_failure,
    REASONING_FORMAT,
)
from app.domain.enums import FootballerBehavior
from app.domain.footballer import Footballer
from app.footballers.cognitive_context import CognitiveFootballerContext
from app.footballers.context import FootballerDecisionContext
from app.footballers.tactical import TacticalFootballer
from app.usage.models import AgentType, make_agent_id

SYSTEM_PROMPT = """You represent one footballer in an abstract simulation.
Choose exactly one behavior: ATTACK, SUPPORT, PRESS, or CONSERVE_ENERGY.
Treat the team tactic as an instruction and consider energy, score, and context.
Your behavior influences probabilities but never determines match outcomes.
Return one valid JSON object only, with exactly these fields:
The behavior value must be exactly "ATTACK", "SUPPORT", "PRESS", or
"CONSERVE_ENERGY". The reason must be plain text between 1 and 160 characters.
Example shape: {"behavior":"SUPPORT","reason":"Keep the team balanced."}
Do not use Markdown, code fences, commentary, or extra fields."""


class CognitiveDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    behavior: FootballerBehavior
    reason: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
    ]


@dataclass(frozen=True)
class CognitiveResponseMetadata:
    response_id: str | None
    model: str | None
    usage: object | None


class CognitiveFootballer:
    def __init__(
        self,
        footballer_name: str,
        *,
        api_key: str | None = None,
        model: str | None = None,
        completion_create: Callable[..., Any] | None = None,
    ) -> None:
        self.footballer_name = footballer_name
        configured_api_key = api_key if api_key is not None else os.getenv("GROQ_API_KEY")
        configured_model = model if model is not None else os.getenv("GROQ_MODEL")
        self._api_key = configured_api_key.strip() if configured_api_key else None
        self.model = configured_model.strip() if configured_model else None
        self._completion_create = completion_create
        self._fallback_decision_maker = TacticalFootballer()
        self.decision_count = 0
        self.provider_call_count = 0
        self.response_metadata: list[CognitiveResponseMetadata] = []
        self.last_error: str | None = None
        self.last_error_category: str | None = None
        self.last_provider_succeeded: bool | None = None
        self.last_used_fallback = False

    def choose_behavior(
        self,
        footballer: Footballer,
        context: CognitiveFootballerContext,
    ) -> FootballerBehavior:
        self.decision_count += 1
        if not self.is_configured:
            return self._fallback(footballer, context, "missing_configuration")

        try:
            completion_create = self._get_completion_create()
            self.provider_call_count += 1
            response = completion_create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": context.model_dump_json()},
                ],
                response_format=JSON_RESPONSE_FORMAT,
                reasoning_format=REASONING_FORMAT,
                temperature=0,
                max_completion_tokens=100,
            )
            self.response_metadata.append(
                CognitiveResponseMetadata(
                    response_id=getattr(response, "id", None),
                    model=getattr(response, "model", self.model),
                    usage=getattr(response, "usage", None),
                )
            )
            content = response.choices[0].message.content
            if not content:
                log_malformed_response(agent_id=self.agent_id, model=self.model)
                return self._fallback(
                    footballer,
                    context,
                    "missing_response",
                    category="MALFORMED_RESPONSE",
                    provider_attempted=True,
                )
            decision = CognitiveDecision.model_validate_json(content)
            self.last_error = None
            self.last_error_category = None
            self.last_provider_succeeded = True
            self.last_used_fallback = False
            return decision.behavior
        except (
            ValidationError,
            ValueError,
            TypeError,
            AttributeError,
            IndexError,
        ) as error:
            log_malformed_response(
                agent_id=self.agent_id,
                model=self.model,
                error=error,
            )
            return self._fallback(
                footballer,
                context,
                "invalid_response",
                category="MALFORMED_RESPONSE",
                provider_attempted=True,
            )
        except Exception as error:
            category = log_provider_failure(
                agent_id=self.agent_id,
                model=self.model,
                error=error,
                api_key=self._api_key,
            )
            return self._fallback(
                footballer,
                context,
                "provider_error",
                category=category,
                provider_attempted=True,
            )

    @property
    def agent_id(self) -> str:
        return make_agent_id(AgentType.COGNITIVE_FOOTBALLER, self.footballer_name)

    @property
    def is_configured(self) -> bool:
        return bool(self.model and (self._completion_create or self._api_key))

    def _get_completion_create(self) -> Callable[..., Any]:
        if self._completion_create is not None:
            return self._completion_create
        return create_completion(self._api_key)

    def _fallback(
        self,
        footballer: Footballer,
        context: CognitiveFootballerContext,
        error_code: str,
        *,
        category: str | None = None,
        provider_attempted: bool = False,
    ) -> FootballerBehavior:
        self.last_error = error_code
        self.last_error_category = category or "CONFIGURATION"
        if provider_attempted:
            self.last_provider_succeeded = False
        self.last_used_fallback = True
        tactical_context = FootballerDecisionContext(
            score_difference=context.score_difference,
            team_tactic=context.team_tactic,
            previous_block_result=context.previous_block_result,
        )
        return self._fallback_decision_maker.choose_behavior(
            footballer,
            tactical_context,
        )
