import re
from decimal import Decimal
from enum import Enum, StrEnum

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing import Annotated


class AgentType(str, Enum):
    ASSISTANT_COACH = "ASSISTANT_COACH"
    COACH = "COACH"
    COGNITIVE_FOOTBALLER = "COGNITIVE_FOOTBALLER"


class ProviderName(StrEnum):
    GROQ = "GROQ"
    GEMINI = "GEMINI"


class UsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: Annotated[str, StringConstraints(min_length=1)]
    agent_type: AgentType
    provider: ProviderName = ProviderName.GROQ
    model: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cached_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    used_fallback: bool = False

    @model_validator(mode="after")
    def validate_token_totals(self) -> "UsageRecord":
        if (
            self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens is not None
            and self.total_tokens != self.input_tokens + self.output_tokens
        ):
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        if (
            self.cached_tokens is not None
            and self.input_tokens is not None
            and self.cached_tokens > self.input_tokens
        ):
            raise ValueError("cached_tokens cannot exceed input_tokens")
        return self


class UsageTotals(BaseModel):
    calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cached_tokens: int = Field(ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=0)


def make_agent_id(agent_type: AgentType, name: str) -> str:
    prefixes = {
        AgentType.ASSISTANT_COACH: "assistant",
        AgentType.COACH: "coach",
        AgentType.COGNITIVE_FOOTBALLER: "footballer",
    }
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return f"{prefixes[agent_type]}:{slug}"
