from app.domain.enums import MatchEventType, MatchPhase
from app.web.presentation import (
    CHANCE_MESSAGES,
    PresentationTimeBucket,
    TimelineEvent,
    _goal_message,
    add_quiet_match_events,
    classify_time,
    scheduled_narrative_minutes,
    select_narrative,
)
from app.domain.enums import TeamTactic
from app.web.session import TeamSide, WebMatchSession


def _selected_session(seed: int) -> WebMatchSession:
    session = WebMatchSession(seed=seed, api_key="", model="")
    session.select_team(TeamSide.TEAM_A)
    session.set_human_tactic(TeamTactic.BALANCED)
    return session


def _complete_match(seed: int) -> tuple[WebMatchSession, list[dict[str, object]]]:
    session = _selected_session(seed)
    responses = [session.start()]
    while session.controller.phase is not MatchPhase.FULL_TIME:
        responses.append(session.continue_match())
    return session, responses


def test_timestamps_are_ordered_and_inside_each_block() -> None:
    _, responses = _complete_match(42)

    for block_number, response in enumerate(responses, start=1):
        playback = response["playback"]
        assert playback is not None
        timeline = playback["timeline"]
        assert [event["tick"] for event in timeline] == sorted(
            event["tick"] for event in timeline
        )
        assert all(0 <= event["tick"] <= 25 for event in timeline)
        assert all(
            event["tick"] > 0
            or (block_number == 1 and event["type"] == "MILESTONE")
            for event in timeline
        )
        assert all(event["block_number"] == block_number for event in timeline)


def test_match_lifecycle_milestones_follow_fixed_block_boundaries() -> None:
    _, responses = _complete_match(42)
    milestones = [
        event
        for response in responses
        for event in response["playback"]["timeline"]
        if event["type"] == "MILESTONE"
    ]

    assert [
        (event["display_minute"], event["text"])
        for event in milestones
    ] == [
        ("0'", "⚽ Kickoff"),
        ("25'", "💧 Hydration break"),
        ("26'", "▶ Play resumes"),
        ("45+5'", "⏸ Half-time"),
        ("46'", "▶ Second half"),
        ("70'", "💧 Hydration break"),
        ("71'", "▶ Play resumes"),
        ("90+5'", "🏁 Full-time"),
    ]
    assert all(event["kind"] == "PRESENTATION" for event in milestones)
    assert len({event["absolute_minute"] for event in milestones}) == 8


def test_milestone_feed_does_not_mutate_match_state_or_duplicate_events() -> None:
    session, responses = _complete_match(17)
    finalized_state = session.controller.state.model_copy(deep=True)
    milestone_keys = [
        (event["absolute_minute"], event["text"])
        for response in responses
        for event in response["playback"]["timeline"]
        if event["type"] == "MILESTONE"
    ]
    final_feed_keys = [
        (event["absolute_minute"], event["text"])
        for event in responses[-1]["presentation_feed"]
        if event["type"] == "MILESTONE"
    ]

    session.state_payload()

    assert session.controller.state == finalized_state
    assert len(milestone_keys) == len(set(milestone_keys)) == 8
    assert final_feed_keys == milestone_keys


def test_stoppage_time_clock_format_is_valid() -> None:
    _, responses = _complete_match(42)

    assert responses[1]["playback"]["clocks"][-5:] == [
        "45+1'",
        "45+2'",
        "45+3'",
        "45+4'",
        "45+5'",
    ]
    assert responses[3]["playback"]["clocks"][-5:] == [
        "90+1'",
        "90+2'",
        "90+3'",
        "90+4'",
        "90+5'",
    ]


def test_same_seed_reproduces_timeline_and_different_seeds_can_vary() -> None:
    first = _selected_session(seed=7).start()["playback"]["timeline"]
    repeated = _selected_session(seed=7).start()["playback"]["timeline"]
    different = _selected_session(seed=8).start()["playback"]["timeline"]

    assert first == repeated
    assert first != different


def test_presentation_event_count_is_not_fixed_per_block() -> None:
    counts = {
        sum(
            event["kind"] == "PRESENTATION" and event["type"] != "QUIET_MATCH"
            for event in _selected_session(seed=seed).start()["playback"]["timeline"]
        )
        for seed in range(10)
    }

    assert len(counts) > 1


def test_timeline_building_does_not_change_finalized_match_state() -> None:
    session = _selected_session(seed=11)
    response = session.start()
    finalized_state = session.controller.state.model_copy(deep=True)

    session.state_payload()

    assert session.controller.state == finalized_state
    assert response["playback"]["final_score"] == response["score"]


def test_goal_feed_matches_backend_goals_and_score_target() -> None:
    session, responses = _complete_match(3)
    shown_goals = sum(
        event["type"] == "GOAL" and event["kind"] == "GAME"
        for response in responses
        for event in response["playback"]["timeline"]
    )
    backend_goals = sum(
        int(block.simulation.team_a_goal) + int(block.simulation.team_b_goal)
        for block in session.controller.completed_blocks
    )

    assert backend_goals > 0
    assert shown_goals == backend_goals
    assert responses[-1]["playback"]["final_score"] == responses[-1]["score"]


def test_narration_has_variety_and_contextual_goal_messages() -> None:
    assert len(CHANCE_MESSAGES) > 1
    assert "breaks the deadlock" in _goal_message(
        "AI United",
        is_team_a=True,
        score_before=(0, 0),
        score_after=(1, 0),
        absolute_minute=20,
    )
    assert "equalizer" in _goal_message(
        "Neural FC",
        is_team_a=False,
        score_before=(1, 0),
        score_after=(1, 1),
        absolute_minute=60,
    )
    assert "strikes late" in _goal_message(
        "AI United",
        is_team_a=True,
        score_before=(1, 1),
        score_after=(2, 1),
        absolute_minute=90,
    )


def test_presentation_categories_do_not_expand_domain_event_types() -> None:
    domain_types = {event_type.value for event_type in MatchEventType}
    timeline = _selected_session(seed=0).start()["playback"]["timeline"]
    presentation_types = {
        event["type"] for event in timeline if event["kind"] == "PRESENTATION"
    }

    assert domain_types == {"GOAL", "CHANCE", "TACTICAL_CHANGE", "ENERGY_WARNING"}
    assert presentation_types.isdisjoint(domain_types)


def _visible_event(tick: int) -> TimelineEvent:
    return TimelineEvent(
        block_number=1,
        tick=tick,
        absolute_minute=tick,
        display_minute=f"{tick}'",
        kind="PRESENTATION",
        type="TEMPO",
        text="The tempo is starting to rise.",
    )


def test_fifteen_minutes_without_activity_adds_quiet_match_event() -> None:
    timeline = add_quiet_match_events(
        [], block_number=1, last_activity_minute=0, match_seed=1
    )

    assert [(event.tick, event.type) for event in timeline] == [(15, "QUIET_MATCH")]


def test_less_than_fifteen_minutes_without_activity_adds_nothing() -> None:
    timeline = add_quiet_match_events(
        [_visible_event(14)],
        block_number=1,
        last_activity_minute=0,
        match_seed=1,
    )

    assert [event.type for event in timeline] == ["TEMPO"]


def test_visible_event_resets_quiet_match_inactivity_count() -> None:
    timeline = add_quiet_match_events(
        [_visible_event(10)],
        block_number=1,
        last_activity_minute=0,
        match_seed=1,
    )

    assert [(event.tick, event.type) for event in timeline] == [
        (10, "TEMPO"),
        (25, "QUIET_MATCH"),
    ]


def test_another_fifteen_minute_gap_can_add_another_quiet_event() -> None:
    timeline = add_quiet_match_events(
        [], block_number=4, last_activity_minute=70, match_seed=1
    )

    assert [(event.absolute_minute, event.type) for event in timeline] == [
        (85, "QUIET_MATCH"),
        (100, "QUIET_MATCH"),
    ]


def test_quiet_messages_are_seeded_and_can_vary() -> None:
    first = add_quiet_match_events(
        [], block_number=1, last_activity_minute=0, match_seed=4
    )
    repeated = add_quiet_match_events(
        [], block_number=1, last_activity_minute=0, match_seed=4
    )
    messages = {
        add_quiet_match_events(
            [], block_number=1, last_activity_minute=0, match_seed=seed
        )[0].text
        for seed in range(12)
    }

    assert first == repeated
    assert len(messages) > 1


def test_time_buckets_follow_displayed_match_time() -> None:
    assert classify_time(12) is PresentationTimeBucket.EARLY
    assert classify_time(40) is PresentationTimeBucket.MID
    assert classify_time(46) is PresentationTimeBucket.STOPPAGE_TIME
    assert classify_time(76) is PresentationTimeBucket.LATE
    assert classify_time(99) is PresentationTimeBucket.STOPPAGE_TIME


def test_early_narration_does_not_use_late_urgency() -> None:
    messages = {
        select_narrative(
            match_seed=seed,
            absolute_minute=12,
            team_a_name="AI United",
            team_b_name="Neural FC",
            score=(0, 0),
        )[1]
        for seed in range(20)
    }

    assert all("running out of time" not in message for message in messages)
    assert all("late winner" not in message for message in messages)
    assert all("protect the lead" not in message for message in messages)


def test_late_narration_reflects_losing_winning_and_drawing_states() -> None:
    losing = {
        select_narrative(
            match_seed=seed,
            absolute_minute=85,
            team_a_name="AI United",
            team_b_name="Neural FC",
            score=(0, 1),
            is_team_a=True,
        )[1]
        for seed in range(20)
    }
    winning = {
        select_narrative(
            match_seed=seed,
            absolute_minute=85,
            team_a_name="AI United",
            team_b_name="Neural FC",
            score=(1, 0),
            is_team_a=True,
        )[1]
        for seed in range(20)
    }
    drawing = {
        select_narrative(
            match_seed=seed,
            absolute_minute=85,
            team_a_name="AI United",
            team_b_name="Neural FC",
            score=(1, 1),
            is_team_a=True,
        )[1]
        for seed in range(20)
    }

    assert any("equalizer" in message or "running out of time" in message for message in losing)
    assert any("protect the lead" in message or "see this out" in message for message in winning)
    assert any("late winner" in message or "decisive goal" in message for message in drawing)
    assert all("protect the lead" not in message for message in losing)
    assert all("equalizer" not in message for message in winning | drawing)


def test_stoppage_narration_is_final_and_context_appropriate() -> None:
    losing = select_narrative(
        match_seed=2,
        absolute_minute=99,
        team_a_name="AI United",
        team_b_name="Neural FC",
        score=(0, 1),
        is_team_a=True,
    )[1]
    drawing = select_narrative(
        match_seed=2,
        absolute_minute=99,
        team_a_name="AI United",
        team_b_name="Neural FC",
        score=(1, 1),
        is_team_a=True,
    )[1]

    assert any(
        word in losing
        for word in ("final", "almost gone", "equalizer", "everything forward")
    )
    assert any(word in drawing for word in ("last", "final", "knife edge", "late winner"))
    assert "beginning to apply pressure" not in losing


def test_first_half_stoppage_does_not_sound_like_full_time() -> None:
    messages = {
        select_narrative(
            match_seed=seed,
            absolute_minute=48,
            team_a_name="AI United",
            team_b_name="Neural FC",
            score=(0, 0),
            is_team_a=True,
        )[1]
        for seed in range(20)
    }

    assert all("at the death" not in message for message in messages)
    assert all("late winner" not in message for message in messages)
    assert all("final seconds" not in message for message in messages)
    assert all("half" in message or "interval" in message or "break" in message for message in messages)


def test_seeded_narrative_gaps_are_reproducible_and_variable() -> None:
    first = scheduled_narrative_minutes(21)
    repeated = scheduled_narrative_minutes(21)
    different = scheduled_narrative_minutes(22)
    gaps = [current - previous for previous, current in zip((0, *first), first)]

    assert first == repeated
    assert first != different
    assert len(set(gaps)) > 1
    assert all(gap in range(5, 19) for gap in gaps)
    assert len({len(scheduled_narrative_minutes(seed)) for seed in range(20)}) > 1


def test_consecutive_narrative_messages_do_not_repeat() -> None:
    _, responses = _complete_match(42)
    messages = [
        event["text"]
        for response in responses
        for event in response["playback"]["timeline"]
        if event["kind"] == "PRESENTATION" and event["type"] != "QUIET_MATCH"
    ]

    assert all(first != second for first, second in zip(messages, messages[1:]))
