from __future__ import annotations

import hashlib
import random
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import MatchEventType, MatchSituation
from app.match.match_controller import CompletedMatchBlock

TICKS_PER_BLOCK = 25
TOTAL_MATCH_TICKS = 100
NARRATIVE_GAPS = (5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 18)

CHANCE_MESSAGES = (
    "Big chance for {team}!",
    "{team} comes very close!",
    "{opponent} survives a dangerous moment!",
    "{team} is knocking on the door!",
    "Great opportunity for {team}!",
)

QUIET_MATCH_MESSAGES = (
    "Not much happening out there...",
    "This match could use a little excitement.",
    "The players seem to be taking it easy.",
    "A quiet spell. Very quiet.",
    "Someone wake the players up!",
    "The crowd is waiting for something to happen.",
    "This one is becoming a tough watch.",
)


class PresentationTimeBucket(str, Enum):
    EARLY = "EARLY"
    MID = "MID"
    LATE = "LATE"
    STOPPAGE_TIME = "STOPPAGE_TIME"


NARRATIVE_TEMPLATES = {
    (PresentationTimeBucket.EARLY, None): (
        ("MOMENTUM", "{team} is settling into the match."),
        ("MOMENTUM", "{team} is beginning to find some rhythm."),
        ("PRESSURE", "{team} starts to apply pressure."),
        ("TEMPO", "Both teams are still feeling their way into the game."),
    ),
    (PresentationTimeBucket.MID, None): (
        ("DOMINANCE", "{team} is starting to take control."),
        ("MOMENTUM", "{team} is growing into the match."),
        ("TEMPO", "The tempo is beginning to rise."),
        ("PRESSURE", "{team} is keeping the pressure on."),
    ),
    (PresentationTimeBucket.LATE, MatchSituation.DRAWING): (
        ("LATE_PUSH", "Both teams are searching for a late winner!"),
        ("LATE_PUSH", "{team} senses a chance to steal this match."),
        ("LATE_PUSH", "{team} is pushing for the decisive goal."),
        ("TEMPO", "The tension is rising as both teams seek a breakthrough."),
    ),
    (PresentationTimeBucket.LATE, MatchSituation.LOSING): (
        ("LATE_PUSH", "{team} is running out of time."),
        ("LATE_PUSH", "{team} is throwing everything forward."),
        ("LATE_PUSH", "{team} is pushing hard for an equalizer."),
        ("REACTION", "{team} needs something quickly."),
    ),
    (PresentationTimeBucket.LATE, MatchSituation.WINNING): (
        ("REACTION", "{team} is trying to protect the lead."),
        ("REACTION", "{team} is managing the final minutes carefully."),
        ("PRESSURE", "{opponent} is applying growing late pressure."),
        ("REACTION", "{team} is working to see this out."),
    ),
    (PresentationTimeBucket.STOPPAGE_TIME, MatchSituation.DRAWING): (
        ("LATE_PUSH", "One last chance to find a winner!"),
        ("LATE_PUSH", "Both teams are making a final push."),
        ("TEMPO", "The match is on a knife edge."),
        ("LATE_PUSH", "A late winner would settle everything now."),
    ),
    (PresentationTimeBucket.STOPPAGE_TIME, MatchSituation.LOSING): (
        ("LATE_PUSH", "{team} throws everything forward!"),
        ("LATE_PUSH", "{team} has one final chance to respond."),
        ("LATE_PUSH", "{team} is desperately searching for an equalizer!"),
        ("REACTION", "Time is almost gone for {team}."),
    ),
    (PresentationTimeBucket.STOPPAGE_TIME, MatchSituation.WINNING): (
        ("REACTION", "{team} is trying to see this out."),
        ("REACTION", "{team} is protecting the lead under heavy pressure."),
        ("REACTION", "{team} is counting down the final seconds."),
        ("REACTION", "{team} is holding on."),
    ),
}

FIRST_HALF_STOPPAGE_TEMPLATES = {
    MatchSituation.DRAWING: (
        ("TEMPO", "Both teams want an edge before half-time."),
        ("LATE_PUSH", "One last push before the interval."),
        ("TEMPO", "The first half is entering its final moments."),
        ("PRESSURE", "{team} is keeping the pressure on before the break."),
    ),
    MatchSituation.LOSING: (
        ("REACTION", "{team} is looking for a response before half-time."),
        ("LATE_PUSH", "{team} wants an equalizer before the interval."),
        ("PRESSURE", "{team} is applying pressure before the break."),
        ("REACTION", "{team} needs a lift before half-time."),
    ),
    MatchSituation.WINNING: (
        ("REACTION", "{team} wants to take the lead into half-time."),
        ("REACTION", "{team} is protecting the advantage before the break."),
        ("PRESSURE", "{opponent} is pressing for a response before half-time."),
        ("TEMPO", "{team} is finishing the half with the lead."),
    ),
}


class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_number: int = Field(ge=1, le=4)
    tick: int = Field(ge=0, le=TICKS_PER_BLOCK)
    absolute_minute: int = Field(ge=0, le=TOTAL_MATCH_TICKS)
    display_minute: str
    kind: Literal["GAME", "PRESENTATION"]
    type: str
    text: str
    team_side: Literal["team_a", "team_b"] | None = None
    score_after: dict[str, int] | None = None


class BlockPlayback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_number: int = Field(ge=1, le=4)
    status_label: str = "MATCH IN PROGRESS"
    clocks: list[str]
    start_progress: int = Field(ge=0, le=100)
    end_progress: int = Field(ge=0, le=100)
    start_score: dict[str, int]
    final_score: dict[str, int]
    start_energy: dict[str, float]
    final_energy: dict[str, float]
    timeline: list[TimelineEvent]


def build_block_playback(
    block: CompletedMatchBlock,
    *,
    block_number: int,
    match_seed: int,
    team_a_name: str,
    team_b_name: str,
    start_score: tuple[int, int],
    start_energy: tuple[float, float],
    last_activity_minute: int = 0,
    last_narrative_text: str | None = None,
) -> BlockPlayback:
    rng = random.Random(_timeline_seed(match_seed, block_number, block))
    game_timeline = _build_game_timeline(
        block,
        block_number=block_number,
        rng=rng,
        team_a_name=team_a_name,
        team_b_name=team_b_name,
        start_score=start_score,
    )
    narrative_timeline = _build_narrative_timeline(
        game_timeline,
        block_number=block_number,
        match_seed=match_seed,
        team_a_name=team_a_name,
        team_b_name=team_b_name,
        start_score=start_score,
        last_narrative_text=last_narrative_text,
    )
    milestone_timeline = _build_milestone_timeline(block_number)
    timeline = sorted(
        game_timeline + narrative_timeline + milestone_timeline,
        key=_timeline_sort_key,
    )
    timeline = add_quiet_match_events(
        timeline,
        block_number=block_number,
        last_activity_minute=last_activity_minute,
        match_seed=match_seed,
    )

    return BlockPlayback(
        block_number=block_number,
        clocks=[
            format_match_minute(block_number, tick)
            for tick in range(1, TICKS_PER_BLOCK + 1)
        ],
        start_progress=(block_number - 1) * TICKS_PER_BLOCK,
        end_progress=block_number * TICKS_PER_BLOCK,
        start_score={"team_a": start_score[0], "team_b": start_score[1]},
        final_score={
            "team_a": block.state.team_a_score,
            "team_b": block.state.team_b_score,
        },
        start_energy={"team_a": start_energy[0], "team_b": start_energy[1]},
        final_energy={
            "team_a": block.state.team_a_average_energy,
            "team_b": block.state.team_b_average_energy,
        },
        timeline=timeline,
    )


def scheduled_narrative_minutes(match_seed: int) -> tuple[int, ...]:
    rng = random.Random(_stable_seed(f"density:{match_seed}"))
    minute = 0
    scheduled: list[int] = []
    while minute < TOTAL_MATCH_TICKS:
        minute += rng.choice(NARRATIVE_GAPS)
        if minute <= TOTAL_MATCH_TICKS:
            scheduled.append(minute)
    return tuple(scheduled)


def classify_time(absolute_minute: int) -> PresentationTimeBucket:
    if absolute_minute in range(46, 51) or absolute_minute in range(96, 101):
        return PresentationTimeBucket.STOPPAGE_TIME
    if absolute_minute <= 30:
        return PresentationTimeBucket.EARLY
    if absolute_minute <= 75:
        return PresentationTimeBucket.MID
    return PresentationTimeBucket.LATE


def select_narrative(
    *,
    match_seed: int,
    absolute_minute: int,
    team_a_name: str,
    team_b_name: str,
    score: tuple[int, int],
    is_team_a: bool | None = None,
    previous_text: str | None = None,
) -> tuple[str, str, str]:
    rng = random.Random(_stable_seed(f"narrative:{match_seed}:{absolute_minute}"))
    if is_team_a is None:
        is_team_a = bool(rng.randrange(2))
    team = team_a_name if is_team_a else team_b_name
    opponent = team_b_name if is_team_a else team_a_name
    situation = _score_situation(score, is_team_a=is_team_a)
    bucket = classify_time(absolute_minute)
    if bucket is PresentationTimeBucket.STOPPAGE_TIME and absolute_minute <= 50:
        templates = FIRST_HALF_STOPPAGE_TEMPLATES[situation]
    else:
        key = (
            bucket,
            None
            if bucket in {PresentationTimeBucket.EARLY, PresentationTimeBucket.MID}
            else situation,
        )
        templates = NARRATIVE_TEMPLATES[key]
    rendered = [
        (category, template.format(team=team, opponent=opponent))
        for category, template in templates
    ]
    choices = [choice for choice in rendered if choice[1] != previous_text] or rendered
    category, text = rng.choice(choices)
    return category, text, team


def add_quiet_match_events(
    timeline: list[TimelineEvent],
    *,
    block_number: int,
    last_activity_minute: int,
    match_seed: int,
) -> list[TimelineEvent]:
    """Fill 15-minute visible-feed gaps without changing simulation state."""
    block_start = (block_number - 1) * TICKS_PER_BLOCK + 1
    block_end = block_number * TICKS_PER_BLOCK
    activity_minute = last_activity_minute
    while activity_minute + 15 < block_start:
        activity_minute += 15
    rng = random.Random(
        _quiet_seed(match_seed, block_number, last_activity_minute, timeline)
    )
    filled: list[TimelineEvent] = []

    for event in sorted(timeline, key=lambda item: item.absolute_minute):
        while event.absolute_minute > activity_minute + 15:
            activity_minute += 15
            filled.append(
                _quiet_event(block_number, activity_minute, rng.choice(QUIET_MATCH_MESSAGES))
            )
        filled.append(event)
        activity_minute = event.absolute_minute

    while block_end >= activity_minute + 15:
        activity_minute += 15
        filled.append(
            _quiet_event(block_number, activity_minute, rng.choice(QUIET_MATCH_MESSAGES))
        )

    return sorted(filled, key=_timeline_sort_key)


def format_match_minute(block_number: int, tick: int) -> str:
    if not 1 <= block_number <= 4 or not 1 <= tick <= TICKS_PER_BLOCK:
        raise ValueError("Block number and tick must identify a match minute.")
    if block_number == 1:
        minute = tick
    elif block_number == 2:
        minute = 25 + tick
        return f"45+{minute - 45}'" if minute > 45 else f"{minute}'"
    elif block_number == 3:
        minute = 45 + tick
    else:
        minute = 70 + tick
        return f"90+{minute - 90}'" if minute > 90 else f"{minute}'"
    return f"{minute}'"


def _build_game_timeline(
    block: CompletedMatchBlock,
    *,
    block_number: int,
    rng: random.Random,
    team_a_name: str,
    team_b_name: str,
    start_score: tuple[int, int],
) -> list[TimelineEvent]:
    available_ticks = list(range(2, TICKS_PER_BLOCK + 1))
    rng.shuffle(available_ticks)
    assigned: list[tuple[int, object]] = []
    for index, event in enumerate(block.events):
        if event.type is MatchEventType.TACTICAL_CHANGE:
            tick = 1
        elif available_ticks:
            tick = available_ticks.pop()
        else:
            tick = 2 + (index % (TICKS_PER_BLOCK - 1))
        assigned.append((tick, event))
    assigned.sort(key=lambda item: (item[0], item[1].type.value))

    score_a, score_b = start_score
    timeline: list[TimelineEvent] = []
    for tick, event in assigned:
        opponent = team_b_name if event.team_name == team_a_name else team_a_name
        score_after = None
        if event.type is MatchEventType.CHANCE:
            text = rng.choice(CHANCE_MESSAGES).format(
                team=event.team_name,
                opponent=opponent,
            )
        elif event.type is MatchEventType.GOAL:
            before = (score_a, score_b)
            if event.team_name == team_a_name:
                score_a += 1
            else:
                score_b += 1
            text = _goal_message(
                event.team_name,
                is_team_a=event.team_name == team_a_name,
                score_before=before,
                score_after=(score_a, score_b),
                absolute_minute=_absolute_minute(block_number, tick),
            )
            score_after = {"team_a": score_a, "team_b": score_b}
        elif event.type is MatchEventType.TACTICAL_CHANGE:
            text = f"{event.team_name} switches to {event.new_tactic.value}."
        else:
            text = (
                f"{event.footballer_name} is running low on energy "
                f"for {event.team_name}."
            )
        absolute_minute = _absolute_minute(block_number, tick)
        timeline.append(
            TimelineEvent(
                block_number=block_number,
                tick=tick,
                absolute_minute=absolute_minute,
                display_minute=format_match_minute(block_number, tick),
                kind="GAME",
                type=event.type.value,
                text=text,
                team_side=(
                    "team_a" if event.team_name == team_a_name else "team_b"
                ),
                score_after=score_after,
            )
        )
    return timeline


def _build_narrative_timeline(
    game_timeline: list[TimelineEvent],
    *,
    block_number: int,
    match_seed: int,
    team_a_name: str,
    team_b_name: str,
    start_score: tuple[int, int],
    last_narrative_text: str | None,
) -> list[TimelineEvent]:
    block_start = (block_number - 1) * TICKS_PER_BLOCK + 1
    block_end = block_number * TICKS_PER_BLOCK
    game_minutes = {event.absolute_minute for event in game_timeline}
    timeline: list[TimelineEvent] = []
    previous_text = last_narrative_text
    for absolute_minute in scheduled_narrative_minutes(match_seed):
        if not block_start <= absolute_minute <= block_end:
            continue
        if absolute_minute in game_minutes:
            continue
        score = _score_at_minute(start_score, game_timeline, absolute_minute)
        category, text, team = select_narrative(
            match_seed=match_seed,
            absolute_minute=absolute_minute,
            team_a_name=team_a_name,
            team_b_name=team_b_name,
            score=score,
            previous_text=previous_text,
        )
        tick = absolute_minute - ((block_number - 1) * TICKS_PER_BLOCK)
        timeline.append(
            TimelineEvent(
                block_number=block_number,
                tick=tick,
                absolute_minute=absolute_minute,
                display_minute=format_match_minute(block_number, tick),
                kind="PRESENTATION",
                type=category,
                text=text,
                team_side="team_a" if team == team_a_name else "team_b",
            )
        )
        previous_text = text
    return timeline


def _build_milestone_timeline(block_number: int) -> list[TimelineEvent]:
    """Create fixed lifecycle markers without adding domain match events."""
    return [
        TimelineEvent(
            block_number=block_number,
            tick=tick,
            absolute_minute=absolute_minute,
            display_minute=display_minute,
            kind="PRESENTATION",
            type="MILESTONE",
            text=text,
        )
        for tick, absolute_minute, display_minute, text in _MILESTONES[block_number]
    ]


def _timeline_sort_key(event: TimelineEvent) -> tuple[int, int]:
    if event.type == "MILESTONE":
        priority = 0 if event.tick <= 1 else 3
    elif event.kind == "GAME":
        priority = 1
    else:
        priority = 2
    return event.absolute_minute, priority


def _score_at_minute(
    start_score: tuple[int, int],
    game_timeline: list[TimelineEvent],
    absolute_minute: int,
) -> tuple[int, int]:
    score_a, score_b = start_score
    for event in game_timeline:
        if event.absolute_minute >= absolute_minute:
            break
        if event.score_after is not None:
            score_a = event.score_after["team_a"]
            score_b = event.score_after["team_b"]
    return score_a, score_b


def _score_situation(
    score: tuple[int, int],
    *,
    is_team_a: bool,
) -> MatchSituation:
    team_score, opponent_score = score if is_team_a else score[::-1]
    if team_score > opponent_score:
        return MatchSituation.WINNING
    if team_score < opponent_score:
        return MatchSituation.LOSING
    return MatchSituation.DRAWING


def _absolute_minute(block_number: int, tick: int) -> int:
    return (block_number - 1) * TICKS_PER_BLOCK + tick


def _timeline_seed(
    match_seed: int,
    block_number: int,
    block: CompletedMatchBlock,
) -> int:
    event_signature = ":".join(
        f"{event.type.value}/{event.team_name}" for event in block.events
    )
    return _stable_seed(f"game:{match_seed}:{block_number}:{event_signature}")


def _quiet_seed(
    match_seed: int,
    block_number: int,
    last_activity_minute: int,
    timeline: list[TimelineEvent],
) -> int:
    signature = ":".join(
        f"{event.absolute_minute}/{event.kind}/{event.type}" for event in timeline
    )
    return _stable_seed(
        f"quiet:{match_seed}:{block_number}:{last_activity_minute}:{signature}"
    )


def _stable_seed(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big")


def _quiet_event(block_number: int, absolute_minute: int, text: str) -> TimelineEvent:
    tick = absolute_minute - ((block_number - 1) * TICKS_PER_BLOCK)
    return TimelineEvent(
        block_number=block_number,
        tick=tick,
        absolute_minute=absolute_minute,
        display_minute=format_match_minute(block_number, tick),
        kind="PRESENTATION",
        type="QUIET_MATCH",
        text=text,
    )


_MILESTONES = {
    1: (
        (0, 0, "0'", "⚽ Kickoff"),
        (25, 25, "25'", "💧 Hydration break"),
    ),
    2: (
        (1, 26, "26'", "▶ Play resumes"),
        (25, 50, "45+5'", "⏸ Half-time"),
    ),
    3: (
        (1, 51, "46'", "▶ Second half"),
        (25, 75, "70'", "💧 Hydration break"),
    ),
    4: (
        (1, 76, "71'", "▶ Play resumes"),
        (25, 100, "90+5'", "🏁 Full-time"),
    ),
}


def _goal_message(
    team: str,
    *,
    is_team_a: bool,
    score_before: tuple[int, int],
    score_after: tuple[int, int],
    absolute_minute: int,
) -> str:
    before_for = score_before[0] if is_team_a else score_before[1]
    before_against = score_before[1] if is_team_a else score_before[0]
    after_for = score_after[0] if is_team_a else score_after[1]
    after_against = score_after[1] if is_team_a else score_after[0]
    equalized = before_for < before_against and after_for == after_against
    took_lead = before_for == before_against and after_for > after_against
    if absolute_minute >= 96 and equalized:
        return f"GOAL! {team} rescues the match in stoppage time!"
    if absolute_minute >= 96 and took_lead:
        return f"GOAL! {team} steals it at the death!"
    if absolute_minute >= 76 and took_lead:
        return f"GOAL! {team} strikes late to take the lead!"
    if equalized:
        return f"GOAL! {team} finds the equalizer!"
    if score_before == (0, 0):
        return f"GOAL! {team} breaks the deadlock!"
    if took_lead:
        return f"GOAL! {team} takes the lead!"
    return f"GOAL! {team} extends the advantage!"
