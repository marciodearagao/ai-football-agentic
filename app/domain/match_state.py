from pydantic import BaseModel, Field

from app.domain.enums import MatchPhase, TeamTactic


class MatchState(BaseModel):
    phase: MatchPhase = MatchPhase.NOT_STARTED
    minute: int = Field(ge=0)
    team_a_score: int = Field(ge=0)
    team_b_score: int = Field(ge=0)
    team_a_tactic: TeamTactic
    team_b_tactic: TeamTactic
    team_a_strength: float = Field(ge=0, le=100)
    team_b_strength: float = Field(ge=0, le=100)
    team_a_average_energy: float = Field(ge=0, le=100)
    team_b_average_energy: float = Field(ge=0, le=100)
    previous_block_result: str | None = None
