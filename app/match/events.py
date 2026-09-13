from pydantic import BaseModel

from app.domain.enums import (
    BlockAdvantage,
    MatchEventType,
    MatchPhase,
    TeamTactic,
)
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.engine.match_engine import BlockSimulationResult


class MatchEvent(BaseModel):
    type: MatchEventType
    team_name: str
    footballer_name: str | None = None
    phase: MatchPhase
    display_minute: str | None = None
    message_key: str | None = None
    previous_tactic: TeamTactic | None = None
    new_tactic: TeamTactic | None = None


def create_tactical_change_event(
    team_name: str,
    previous_tactic: TeamTactic,
    new_tactic: TeamTactic,
    phase: MatchPhase,
    display_minute: str,
) -> MatchEvent | None:
    if new_tactic is previous_tactic:
        return None
    return MatchEvent(
        type=MatchEventType.TACTICAL_CHANGE,
        team_name=team_name,
        phase=phase,
        display_minute=display_minute,
        message_key="coach_tactic_changed",
        previous_tactic=previous_tactic,
        new_tactic=new_tactic,
    )


def score_after_block(
    team_a_score: int,
    team_b_score: int,
    result: BlockSimulationResult,
) -> tuple[int, int]:
    return (
        team_a_score + int(result.team_a_goal),
        team_b_score + int(result.team_b_goal),
    )


def determine_block_advantage(result: BlockSimulationResult) -> BlockAdvantage:
    if result.team_a_goal != result.team_b_goal:
        return (
            BlockAdvantage.TEAM_A_ADVANTAGE
            if result.team_a_goal
            else BlockAdvantage.TEAM_B_ADVANTAGE
        )
    if result.team_a_chance != result.team_b_chance:
        return (
            BlockAdvantage.TEAM_A_ADVANTAGE
            if result.team_a_chance
            else BlockAdvantage.TEAM_B_ADVANTAGE
        )
    return BlockAdvantage.BALANCED


def create_block_events(
    result: BlockSimulationResult,
    team_a: Team,
    team_b: Team,
    phase: MatchPhase,
    display_minute: str,
    team_a_energy_warnings: list[Footballer],
    team_b_energy_warnings: list[Footballer],
) -> list[MatchEvent]:
    events: list[MatchEvent] = []
    event_flags = (
        (result.team_a_chance, MatchEventType.CHANCE, team_a.name),
        (result.team_b_chance, MatchEventType.CHANCE, team_b.name),
        (result.team_a_goal, MatchEventType.GOAL, team_a.name),
        (result.team_b_goal, MatchEventType.GOAL, team_b.name),
    )
    for occurred, event_type, team_name in event_flags:
        if occurred:
            events.append(
                MatchEvent(
                    type=event_type,
                    team_name=team_name,
                    phase=phase,
                    display_minute=display_minute,
                )
            )

    for team, footballers in (
        (team_a, team_a_energy_warnings),
        (team_b, team_b_energy_warnings),
    ):
        events.extend(
            MatchEvent(
                type=MatchEventType.ENERGY_WARNING,
                team_name=team.name,
                footballer_name=footballer.name,
                phase=phase,
                display_minute=display_minute,
            )
            for footballer in footballers
        )

    return events
