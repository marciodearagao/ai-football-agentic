from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import MatchPhase, MatchSituation, TeamTactic
from app.domain.match_state import MatchState
from app.footballers.context import (
    PreviousBlockResult,
    previous_block_result_for_team,
)


class CoachContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: MatchPhase
    team_score: int = Field(ge=0)
    opponent_score: int = Field(ge=0)
    situation: MatchSituation
    current_tactic: TeamTactic
    team_average_energy: float = Field(ge=0, le=100)
    opponent_average_energy: float = Field(ge=0, le=100)
    team_strength: float = Field(ge=0, le=100)
    opponent_strength: float = Field(ge=0, le=100)
    previous_block_result: PreviousBlockResult | None = None

    @classmethod
    def from_match_state(
        cls,
        state: MatchState,
        *,
        is_team_a: bool,
        phase: MatchPhase,
    ) -> "CoachContext":
        team_score = state.team_a_score if is_team_a else state.team_b_score
        opponent_score = state.team_b_score if is_team_a else state.team_a_score
        if team_score > opponent_score:
            situation = MatchSituation.WINNING
        elif team_score < opponent_score:
            situation = MatchSituation.LOSING
        else:
            situation = MatchSituation.DRAWING

        return cls(
            phase=phase,
            team_score=team_score,
            opponent_score=opponent_score,
            situation=situation,
            current_tactic=(
                state.team_a_tactic if is_team_a else state.team_b_tactic
            ),
            team_average_energy=(
                state.team_a_average_energy
                if is_team_a
                else state.team_b_average_energy
            ),
            opponent_average_energy=(
                state.team_b_average_energy
                if is_team_a
                else state.team_a_average_energy
            ),
            team_strength=(
                state.team_a_strength if is_team_a else state.team_b_strength
            ),
            opponent_strength=(
                state.team_b_strength if is_team_a else state.team_a_strength
            ),
            previous_block_result=previous_block_result_for_team(
                state.previous_block_result,
                is_team_a=is_team_a,
            ),
        )
