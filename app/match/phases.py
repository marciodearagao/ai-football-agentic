from dataclasses import dataclass

from app.domain.enums import MatchPhase


@dataclass(frozen=True)
class MatchBlockDefinition:
    phase: MatchPhase
    start_minute: str
    end_minute: str
    state_minute: int
    next_phase: MatchPhase
    pause_label: str


MATCH_BLOCKS = (
    MatchBlockDefinition(
        phase=MatchPhase.FIRST_BLOCK,
        start_minute="1'",
        end_minute="25'",
        state_minute=25,
        next_phase=MatchPhase.FIRST_HYDRATION,
        pause_label="Hydration Break",
    ),
    MatchBlockDefinition(
        phase=MatchPhase.SECOND_BLOCK,
        start_minute="26'",
        end_minute="45+5'",
        state_minute=45,
        next_phase=MatchPhase.HALF_TIME,
        pause_label="Half-time",
    ),
    MatchBlockDefinition(
        phase=MatchPhase.THIRD_BLOCK,
        start_minute="46'",
        end_minute="70'",
        state_minute=70,
        next_phase=MatchPhase.SECOND_HYDRATION,
        pause_label="Hydration Break",
    ),
    MatchBlockDefinition(
        phase=MatchPhase.FOURTH_BLOCK,
        start_minute="71'",
        end_minute="90+5'",
        state_minute=90,
        next_phase=MatchPhase.FULL_TIME,
        pause_label="Full-time",
    ),
)

CONTINUATION_PHASES = {
    MatchPhase.FIRST_HYDRATION: 1,
    MatchPhase.HALF_TIME: 2,
    MatchPhase.SECOND_HYDRATION: 3,
}
