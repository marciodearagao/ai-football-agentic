from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import MatchPhase, MatchSituation, TeamTactic
from app.domain.footballer import Footballer
from app.footballers.context import PreviousBlockResult


class CognitiveFootballerContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: MatchPhase
    score_difference: int
    situation: MatchSituation
    footballer_energy: float = Field(ge=0, le=100)
    footballer_skill: float = Field(ge=0, le=100)
    footballer_stamina: float = Field(ge=0, le=100)
    footballer_intelligence: float = Field(ge=0, le=100)
    team_tactic: TeamTactic
    team_average_energy: float = Field(ge=0, le=100)
    opponent_average_energy: float = Field(ge=0, le=100)
    previous_block_result: PreviousBlockResult | None = None

    @classmethod
    def for_footballer(
        cls,
        footballer: Footballer,
        *,
        phase: MatchPhase,
        score_difference: int,
        team_tactic: TeamTactic,
        team_average_energy: float,
        opponent_average_energy: float,
        previous_block_result: PreviousBlockResult | None,
    ) -> "CognitiveFootballerContext":
        if score_difference > 0:
            situation = MatchSituation.WINNING
        elif score_difference < 0:
            situation = MatchSituation.LOSING
        else:
            situation = MatchSituation.DRAWING

        return cls(
            phase=phase,
            score_difference=score_difference,
            situation=situation,
            footballer_energy=footballer.energy,
            footballer_skill=footballer.skill,
            footballer_stamina=footballer.stamina,
            footballer_intelligence=footballer.intelligence,
            team_tactic=team_tactic,
            team_average_energy=team_average_energy,
            opponent_average_energy=opponent_average_energy,
            previous_block_result=previous_block_result,
        )
