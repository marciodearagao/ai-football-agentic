import logging
import re
import ssl
from dataclasses import dataclass

from groq import DefaultHttpxClient, Groq


LOGGER = logging.getLogger("ai_football_agentic.groq")

JSON_RESPONSE_FORMAT = {"type": "json_object"}
REASONING_FORMAT = "hidden"


@dataclass(frozen=True)
class ProviderErrorDetails:
    status: int | None
    error_type: str
    category: str
    message: str


def create_completion(api_key: str | None):
    ssl_context = ssl.create_default_context()
    client = Groq(
        api_key=api_key,
        http_client=DefaultHttpxClient(verify=ssl_context),
    )
    return client.chat.completions.create


def log_provider_failure(
    *,
    agent_id: str,
    model: str | None,
    error: Exception,
    api_key: str | None,
) -> str:
    details = provider_error_details(error, api_key=api_key)
    LOGGER.error(
        "Groq request failed\n"
        "agent=%s model=%s status=%s type=%s category=%s\n"
        "message=%s\n"
        "fallback=deterministic",
        agent_id,
        model or "unknown",
        details.status if details.status is not None else "unavailable",
        details.error_type,
        details.category,
        details.message,
    )
    return details.category


def log_malformed_response(
    *,
    agent_id: str,
    model: str | None,
    error: Exception | None = None,
) -> None:
    detail = _validation_detail(error)
    LOGGER.error(
        "Groq response rejected\n"
        "agent=%s model=%s status=unavailable type=ValidationError "
        "category=MALFORMED_RESPONSE\n"
        "message=Response did not match the required JSON contract%s.\n"
        "fallback=deterministic",
        agent_id,
        model or "unknown",
        detail,
    )


def provider_error_details(
    error: Exception,
    *,
    api_key: str | None = None,
) -> ProviderErrorDetails:
    status = getattr(error, "status_code", None)
    status = status if isinstance(status, int) else None
    body = getattr(error, "body", None)
    body_error = body.get("error", body) if isinstance(body, dict) else None

    provider_type = None
    provider_message = None
    if isinstance(body_error, dict):
        provider_type = body_error.get("type") or body_error.get("code")
        provider_message = body_error.get("message")

    error_type = str(provider_type or type(error).__name__)
    category = _category_for(status, error_type)
    message = _sanitize_message(str(provider_message or error), api_key=api_key)
    return ProviderErrorDetails(
        status=status,
        error_type=_sanitize_message(error_type, api_key=api_key),
        category=category,
        message=message,
    )


def _category_for(status: int | None, error_type: str) -> str:
    normalized_type = error_type.lower()
    if status in {401, 403} or "auth" in normalized_type:
        return "AUTHENTICATION"
    if status == 429 or "rate" in normalized_type:
        return "RATE_LIMIT"
    if (
        status == 400
        or "badrequest" in normalized_type
        or "invalid_request" in normalized_type
    ):
        return "INVALID_REQUEST"
    return "PROVIDER_ERROR"


def _sanitize_message(message: str, *, api_key: str | None) -> str:
    sanitized = message
    if api_key:
        sanitized = sanitized.replace(api_key, "[REDACTED]")
    sanitized = re.sub(r"(?i)Bearer\s+[^\s,;]+", "Bearer [REDACTED]", sanitized)
    sanitized = re.sub(r"\bgsk_[A-Za-z0-9_-]+", "[REDACTED]", sanitized)
    sanitized = " ".join(sanitized.split())
    return sanitized[:400] or "No provider error message was supplied."


def _validation_detail(error: Exception | None) -> str:
    errors = getattr(error, "errors", None)
    if not callable(errors):
        return ""
    summaries = []
    for issue in errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in issue.get("loc", ())) or "root"
        summaries.append(f"{location}:{issue.get('type', 'invalid')}")
    return f" ({', '.join(summaries[:3])})" if summaries else ""
