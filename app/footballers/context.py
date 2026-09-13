from enum import Enum

from pydantic import BaseModel

from app.domain.enums import BlockAdvantage, TeamTactic


class PreviousBlockResult(str, Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class FootballerDecisionContext(BaseModel):
    score_difference: int
    team_tactic: TeamTactic
    previous_block_result: PreviousBlockResult | None = None


def previous_block_result_for_team(
    previous_result: str | None,
    *,
    is_team_a: bool,
) -> PreviousBlockResult | None:
    if previous_result is None:
        return None
    try:
        advantage = BlockAdvantage(previous_result)
    except ValueError:
        return None
    if advantage is BlockAdvantage.BALANCED:
        return PreviousBlockResult.NEUTRAL

    team_had_advantage = (
        advantage is BlockAdvantage.TEAM_A_ADVANTAGE
        if is_team_a
        else advantage is BlockAdvantage.TEAM_B_ADVANTAGE
    )
    return (
        PreviousBlockResult.POSITIVE
        if team_had_advantage
        else PreviousBlockResult.NEGATIVE
    )
