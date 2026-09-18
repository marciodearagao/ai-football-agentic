import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from app.agents.coach_context import CoachContext
from app.agents.coach_tools import (
    COACH_TOOL_SCHEMAS,
    ToolExecutionError,
    execute_coach_tool,
)
from app.agents.gemini_support import (
    create_generate_content,
    DEFAULT_GEMINI_MODEL,
    final_decision_config,
    function_response_content,
    log_gemini_failure,
    log_gemini_malformed_response,
    tool_selection_config,
    user_content,
)
from app.agents.groq_support import (
    JSON_RESPONSE_FORMAT,
    create_completion,
    log_malformed_response,
    log_provider_failure,
    REASONING_FORMAT,
)
from app.domain.enums import TeamTactic
from app.usage.models import AgentType, make_agent_id, ProviderName

SYSTEM_PROMPT = """You manage one football team in an abstract simulation.
Choose exactly one tactic: ATTACK, BALANCED, or DEFEND.
Use the available read-only tools when you need current match information.
Your choice influences probabilities but never determines the outcome.
Return one valid JSON object only, with exactly these fields:
The tactic value must be exactly "ATTACK", "BALANCED", or "DEFEND".
The reason must be plain text between 1 and 160 characters.
Example shape: {"tactic":"BALANCED","reason":"Keep a compact shape."}
Do not use Markdown, code fences, commentary, or extra fields."""

DECISION_PROMPT = """Choose the tactic for the upcoming match block.
You may call any of the available read-only tools before answering.
Return the final decision using the required JSON contract."""


class CoachDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tactic: TeamTactic
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


@dataclass(frozen=True)
class CoachResponseMetadata:
    provider: ProviderName
    response_id: str | None
    model: str | None
    usage: object | None


class CoachAgent:
    system_prompt = SYSTEM_PROMPT

    def __init__(
        self,
        team_name: str,
        *,
        api_key: str | None = None,
        model: str | None = None,
        completion_create: Callable[..., Any] | None = None,
        gemini_api_key: str | None = None,
        gemini_model: str | None = None,
        gemini_generate_content: Callable[..., Any] | None = None,
    ) -> None:
        self.team_name = team_name
        configured_api_key = api_key if api_key is not None else os.getenv("GROQ_API_KEY")
        configured_model = model if model is not None else os.getenv("GROQ_MODEL")
        self._api_key = configured_api_key.strip() if configured_api_key else None
        self.model = configured_model.strip() if configured_model else None
        self._completion_create = completion_create
        configured_gemini_key = (
            gemini_api_key
            if gemini_api_key is not None
            else os.getenv("GEMINI_API_KEY")
        )
        configured_gemini_model = (
            gemini_model
            if gemini_model is not None
            else os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        )
        self._gemini_api_key = (
            configured_gemini_key.strip() if configured_gemini_key else None
        )
        self.gemini_model = (
            configured_gemini_model.strip() if configured_gemini_model else None
        )
        self._gemini_generate_content = gemini_generate_content
        self.decision_count = 0
        self.provider_call_count = 0
        self.response_metadata: list[CoachResponseMetadata] = []
        self.last_error: str | None = None
        self.last_error_category: str | None = None
        self.last_provider_succeeded: bool | None = None
        self.last_successful_provider: ProviderName | None = None
        self.last_used_fallback = False

    def choose_tactic(self, context: CoachContext) -> CoachDecision:
        self.decision_count += 1
        if not self.is_configured:
            return self._fallback(context.current_tactic, "missing_configuration")

        attempted = False
        failure = ("provider_error", "PROVIDER_ERROR")
        if self.is_groq_configured:
            attempted = True
            try:
                decision = self._choose_with_groq(context)
            except Exception as error:
                failure = self._handle_provider_failure(
                    ProviderName.GROQ,
                    error,
                )
            else:
                return self._accept(decision, ProviderName.GROQ)

        if self.is_gemini_configured:
            attempted = True
            try:
                decision = self._choose_with_gemini(context)
            except Exception as error:
                failure = self._handle_provider_failure(
                    ProviderName.GEMINI,
                    error,
                )
            else:
                return self._accept(decision, ProviderName.GEMINI)

        return self._fallback(
            context.current_tactic,
            failure[0],
            category=failure[1],
            provider_attempted=attempted,
        )

    @property
    def agent_id(self) -> str:
        return make_agent_id(AgentType.COACH, self.team_name)

    @property
    def is_configured(self) -> bool:
        return self.is_groq_configured or self.is_gemini_configured

    @property
    def is_groq_configured(self) -> bool:
        return bool(self.model and (self._completion_create or self._api_key))

    @property
    def is_gemini_configured(self) -> bool:
        return bool(
            self.gemini_model
            and (self._gemini_generate_content or self._gemini_api_key)
        )

    def _get_completion_create(self) -> Callable[..., Any]:
        if self._completion_create is not None:
            return self._completion_create
        return create_completion(self._api_key)

    def _get_gemini_generate_content(self) -> Callable[..., Any]:
        if self._gemini_generate_content is not None:
            return self._gemini_generate_content
        return create_generate_content(self._gemini_api_key)

    def _choose_with_groq(self, context: CoachContext) -> CoachDecision:
        completion_create = self._get_completion_create()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": DECISION_PROMPT},
        ]
        response = self._request_groq(
            completion_create,
            model=self.model,
            messages=messages,
            tools=list(COACH_TOOL_SCHEMAS),
            tool_choice="auto",
            reasoning_format=REASONING_FORMAT,
            temperature=0,
            max_completion_tokens=100,
        )
        message = self._groq_message(response)
        tool_calls = getattr(message, "tool_calls", None) or []
        if tool_calls:
            messages.append(self._assistant_tool_message(message, tool_calls))
            for tool_call in tool_calls:
                function = getattr(tool_call, "function", None)
                call_id = getattr(tool_call, "id", None)
                if function is None or not call_id:
                    raise ToolExecutionError("Malformed coach tool call.")
                result = execute_coach_tool(
                    getattr(function, "name", None),
                    getattr(function, "arguments", None),
                    context,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": function.name,
                        "content": result,
                    }
                )
            response = self._request_groq(
                completion_create,
                model=self.model,
                messages=messages,
                response_format=JSON_RESPONSE_FORMAT,
                reasoning_format=REASONING_FORMAT,
                temperature=0,
                max_completion_tokens=100,
            )
            message = self._groq_message(response)
            if getattr(message, "tool_calls", None):
                raise ToolExecutionError("Unexpected tool call in final response.")
        return self._validated_decision(getattr(message, "content", None))

    def _choose_with_gemini(self, context: CoachContext) -> CoachDecision:
        generate_content = self._get_gemini_generate_content()
        initial_content = user_content(DECISION_PROMPT)
        response = self._request_gemini(
            generate_content,
            model=self.gemini_model,
            contents=[initial_content],
            config=tool_selection_config(self.system_prompt),
        )
        tool_calls = getattr(response, "function_calls", None) or []
        if tool_calls:
            results: list[tuple[str, dict[str, Any]]] = []
            for tool_call in tool_calls:
                name = getattr(tool_call, "name", None)
                arguments = getattr(tool_call, "args", None) or {}
                result = execute_coach_tool(
                    name,
                    json.dumps(arguments),
                    context,
                )
                results.append((name, json.loads(result)))
            try:
                function_call_content = response.candidates[0].content
            except (AttributeError, IndexError, TypeError) as error:
                raise ValueError("Malformed Gemini tool response.") from error
            response = self._request_gemini(
                generate_content,
                model=self.gemini_model,
                contents=[
                    initial_content,
                    function_call_content,
                    function_response_content(results),
                ],
                config=final_decision_config(
                    self.system_prompt,
                    CoachDecision,
                ),
            )
            if getattr(response, "function_calls", None):
                raise ToolExecutionError("Unexpected Gemini final tool call.")
        return self._validated_decision(getattr(response, "text", None))

    @staticmethod
    def _groq_message(response: Any) -> Any:
        try:
            return response.choices[0].message
        except (AttributeError, IndexError, TypeError) as error:
            raise ValueError("Malformed Groq response.") from error

    @staticmethod
    def _validated_decision(content: str | None) -> CoachDecision:
        if not content:
            raise ValueError("Missing provider response.")
        return CoachDecision.model_validate_json(content)

    def _request_groq(
        self,
        completion_create: Callable[..., Any],
        **kwargs: Any,
    ) -> Any:
        self.provider_call_count += 1
        try:
            response = completion_create(**kwargs)
        except Exception:
            self.response_metadata.append(
                CoachResponseMetadata(
                    provider=ProviderName.GROQ,
                    response_id=None,
                    model=self.model,
                    usage=None,
                )
            )
            raise
        self.response_metadata.append(
            CoachResponseMetadata(
                provider=ProviderName.GROQ,
                response_id=getattr(response, "id", None),
                model=getattr(response, "model", self.model),
                usage=getattr(response, "usage", None),
            )
        )
        return response

    def _request_gemini(
        self,
        generate_content: Callable[..., Any],
        **kwargs: Any,
    ) -> Any:
        self.provider_call_count += 1
        try:
            response = generate_content(**kwargs)
        except Exception:
            self.response_metadata.append(
                CoachResponseMetadata(
                    provider=ProviderName.GEMINI,
                    response_id=None,
                    model=self.gemini_model,
                    usage=None,
                )
            )
            raise
        self.response_metadata.append(
            CoachResponseMetadata(
                provider=ProviderName.GEMINI,
                response_id=getattr(response, "response_id", None),
                model=getattr(response, "model_version", self.gemini_model),
                usage=getattr(response, "usage_metadata", None),
            )
        )
        return response

    def _handle_provider_failure(
        self,
        provider: ProviderName,
        error: Exception,
    ) -> tuple[str, str]:
        if isinstance(error, ToolExecutionError):
            return "tool_execution_failed", "TOOL_EXECUTION"
        if isinstance(error, (ValidationError, ValueError, TypeError)):
            if provider is ProviderName.GROQ:
                log_malformed_response(
                    agent_id=self.agent_id,
                    model=self.model,
                    error=error,
                )
            else:
                log_gemini_malformed_response(
                    agent_id=self.agent_id,
                    model=self.gemini_model,
                )
            return "invalid_response", "MALFORMED_RESPONSE"
        if provider is ProviderName.GROQ:
            category = log_provider_failure(
                agent_id=self.agent_id,
                model=self.model,
                error=error,
                api_key=self._api_key,
            )
        else:
            category = log_gemini_failure(
                agent_id=self.agent_id,
                model=self.gemini_model,
                error=error,
                api_key=self._gemini_api_key,
            )
        return "provider_error", category

    def _accept(
        self,
        decision: CoachDecision,
        provider: ProviderName,
    ) -> CoachDecision:
        self.last_error = None
        self.last_error_category = None
        self.last_provider_succeeded = True
        self.last_successful_provider = provider
        self.last_used_fallback = False
        return decision

    @staticmethod
    def _assistant_tool_message(message: Any, tool_calls: list[Any]) -> dict[str, Any]:
        serialized_calls = []
        for tool_call in tool_calls:
            function = getattr(tool_call, "function", None)
            serialized_calls.append(
                {
                    "id": getattr(tool_call, "id", None),
                    "type": getattr(tool_call, "type", "function"),
                    "function": {
                        "name": getattr(function, "name", None),
                        "arguments": getattr(function, "arguments", None),
                    },
                }
            )
        return {
            "role": "assistant",
            "content": getattr(message, "content", None),
            "tool_calls": serialized_calls,
        }

    def _fallback(
        self,
        tactic: TeamTactic,
        error_code: str,
        *,
        category: str | None = None,
        provider_attempted: bool = False,
    ) -> CoachDecision:
        self.last_error = error_code
        self.last_error_category = category or "CONFIGURATION"
        if provider_attempted:
            self.last_provider_succeeded = False
        self.last_successful_provider = None
        self.last_used_fallback = True
        return CoachDecision(
            tactic=tactic,
            reason=f"fallback_{error_code}",
        )
