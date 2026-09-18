import logging
from collections.abc import Callable
from typing import Any

from google import genai
from google.genai import types

from app.agents.coach_tools import COACH_TOOL_SCHEMAS
from app.agents.groq_support import provider_error_details


LOGGER = logging.getLogger("ai_football_agentic.gemini")
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"


def create_generate_content(api_key: str | None) -> Callable[..., Any]:
    client = genai.Client(api_key=api_key)
    return client.models.generate_content


def tool_selection_config(system_prompt: str) -> types.GenerateContentConfig:
    declarations = [
        types.FunctionDeclaration(
            name=schema["function"]["name"],
            description=schema["function"]["description"],
            parameters_json_schema=schema["function"]["parameters"],
        )
        for schema in COACH_TOOL_SCHEMAS
    ]
    return types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=[types.Tool(function_declarations=declarations)],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="AUTO")
        ),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        ),
        temperature=0,
        max_output_tokens=100,
    )


def final_decision_config(
    system_prompt: str,
    response_schema: type,
) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=response_schema,
        temperature=0,
        max_output_tokens=100,
    )


def user_content(text: str) -> types.Content:
    return types.Content(
        role="user",
        parts=[types.Part.from_text(text=text)],
    )


def function_response_content(
    results: list[tuple[str, dict[str, Any]]],
) -> types.Content:
    return types.Content(
        role="user",
        parts=[
            types.Part.from_function_response(
                name=name,
                response={"result": result},
            )
            for name, result in results
        ],
    )


def log_gemini_failure(
    *,
    agent_id: str,
    model: str | None,
    error: Exception,
    api_key: str | None,
) -> str:
    details = provider_error_details(error, api_key=api_key)
    LOGGER.error(
        "Gemini request failed\n"
        "agent=%s model=%s status=%s type=%s category=%s\n"
        "message=Provider request failed; sensitive response details omitted.\n"
        "fallback=deterministic",
        agent_id,
        model or "unknown",
        details.status if details.status is not None else "unavailable",
        details.error_type,
        details.category,
    )
    return details.category


def log_gemini_malformed_response(
    *,
    agent_id: str,
    model: str | None,
) -> None:
    LOGGER.error(
        "Gemini response rejected\n"
        "agent=%s model=%s status=unavailable type=ValidationError "
        "category=MALFORMED_RESPONSE\n"
        "message=Response did not match the required decision contract.\n"
        "fallback=deterministic",
        agent_id,
        model or "unknown",
    )
