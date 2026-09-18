import json
from collections.abc import Callable
from typing import Any

from app.agents.coach_context import CoachContext


class ToolExecutionError(ValueError):
    """Raised when a coach requests an unsupported or malformed local tool."""


def get_score(context: CoachContext) -> dict[str, int]:
    return {
        "team_score": context.team_score,
        "opponent_score": context.opponent_score,
    }


def get_match_phase(context: CoachContext) -> dict[str, str]:
    return {"match_phase": context.phase.value}


def get_team_energy(context: CoachContext) -> dict[str, float]:
    return {"team_energy": context.team_average_energy}


def get_opponent_energy(context: CoachContext) -> dict[str, float]:
    return {"opponent_energy": context.opponent_average_energy}


def get_current_tactic(context: CoachContext) -> dict[str, str]:
    return {"current_tactic": context.current_tactic.value}


_TOOL_FUNCTIONS: dict[str, Callable[[CoachContext], dict[str, Any]]] = {
    "get_score": get_score,
    "get_match_phase": get_match_phase,
    "get_team_energy": get_team_energy,
    "get_opponent_energy": get_opponent_energy,
    "get_current_tactic": get_current_tactic,
}


def _tool_schema(name: str, description: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    }


COACH_TOOL_SCHEMAS = (
    _tool_schema(
        "get_score",
        "Read the team's score and the opponent's score from the current match state.",
    ),
    _tool_schema("get_match_phase", "Read the current match phase."),
    _tool_schema("get_team_energy", "Read the team's current average energy."),
    _tool_schema(
        "get_opponent_energy",
        "Read the opponent's current average energy.",
    ),
    _tool_schema("get_current_tactic", "Read the team's current tactic."),
)


def execute_coach_tool(
    name: str | None,
    arguments: str | None,
    context: CoachContext,
) -> str:
    """Execute one approved read-only lookup against a bounded context view."""
    function = _TOOL_FUNCTIONS.get(name or "")
    if function is None:
        raise ToolExecutionError("Unknown coach tool.")

    try:
        parsed_arguments = json.loads(arguments or "{}")
    except (json.JSONDecodeError, TypeError) as error:
        raise ToolExecutionError("Coach tool arguments must be valid JSON.") from error
    if parsed_arguments != {}:
        raise ToolExecutionError("Coach tools do not accept arguments.")

    return json.dumps(function(context), separators=(",", ":"))
