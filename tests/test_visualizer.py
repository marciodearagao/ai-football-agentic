from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.domain.enums import TeamTactic
from app.main import create_app
from app.web.session import TeamSide, WebMatchSession
from app.web.visualizer import visual_state_for_event, visualizer_payload


@pytest.mark.parametrize(
    ("event_type", "team_side", "mode", "attacking_side"),
    [
        ("TEMPO", "team_a", "NEUTRAL", None),
        ("QUIET_MATCH", None, "NEUTRAL", None),
        ("PRESSURE", "team_a", "PRESSURE", "team_a"),
        ("MOMENTUM", "team_b", "PRESSURE", "team_b"),
        ("DOMINANCE", "team_a", "PRESSURE", "team_a"),
        ("LATE_PUSH", "team_b", "PRESSURE", "team_b"),
        ("REACTION", "team_a", "PRESSURE", "team_a"),
        ("CHANCE", "team_b", "CHANCE", "team_b"),
        ("GOAL", "team_a", "GOAL", "team_a"),
    ],
)
def test_resolved_events_map_to_predefined_visual_states(
    event_type: str,
    team_side: str | None,
    mode: str,
    attacking_side: str | None,
) -> None:
    frame = visual_state_for_event(event_type, team_side)

    assert frame.mode == mode
    assert frame.attacking_side == attacking_side


def test_visualizer_contract_contains_only_presentation_configuration() -> None:
    payload = visualizer_payload("AI United", "Neural FC")

    assert payload["schema_version"] == 1
    assert payload["teams"] == {
        "team_a": {"name": "AI United"},
        "team_b": {"name": "Neural FC"},
    }
    assert payload["frame"] == {"mode": "NEUTRAL", "attacking_side": None}
    assert set(payload["animation_targets"]) == {"team_a", "team_b"}
    assert "score" not in payload
    assert "probability" not in payload
    assert "possession" not in payload
    assert "outcome" not in payload


def test_starting_formations_are_complete_and_stay_in_their_own_halves() -> None:
    formations = visualizer_payload("AI United", "Neural FC")["formations"]
    expected_roles = {
        "GOALKEEPER": 1,
        "DEFENDER": 4,
        "MIDFIELDER": 3,
        "ATTACKER": 3,
    }

    for side in ("team_a", "team_b"):
        markers = formations[side]
        assert len(markers) == 11
        assert {
            role: sum(marker["role"] == role for marker in markers)
            for role in expected_roles
        } == expected_roles
        assert all(0 <= marker["y"] <= 60 for marker in markers)

    assert all(marker["x"] < 50 for marker in formations["team_a"])
    assert all(marker["x"] > 50 for marker in formations["team_b"])
    assert all(
        team_a["x"] + team_b["x"] == 100
        for team_a, team_b in zip(
            formations["team_a"],
            formations["team_b"],
            strict=True,
        )
    )


@pytest.mark.parametrize(
    ("attacking_side", "opponent_side", "crossed_midfield"),
    [
        ("team_a", "team_b", lambda x: x > 50),
        ("team_b", "team_a", lambda x: x < 50),
    ],
)
def test_pressure_targets_allow_both_teams_to_cross_midfield(
    attacking_side: str,
    opponent_side: str,
    crossed_midfield: Callable[[float], bool],
) -> None:
    targets = visualizer_payload("AI United", "Neural FC")["animation_targets"]
    pressure = targets[attacking_side]["PRESSURE"]
    advanced_players = [
        marker
        for marker in pressure[attacking_side]
        if marker["role"] in {"MIDFIELDER", "ATTACKER"}
        and crossed_midfield(marker["x"])
    ]

    assert len(advanced_players) >= 5
    assert pressure[opponent_side]


@pytest.mark.parametrize(
    ("attacking_side", "in_final_third", "near_goal"),
    [
        ("team_a", lambda x: x > 66, lambda x: x >= 90),
        ("team_b", lambda x: x < 34, lambda x: x <= 10),
    ],
)
def test_chance_and_goal_targets_reach_both_final_thirds(
    attacking_side: str,
    in_final_third: Callable[[float], bool],
    near_goal: Callable[[float], bool],
) -> None:
    targets = visualizer_payload("AI United", "Neural FC")["animation_targets"]
    chance_players = targets[attacking_side]["CHANCE"][attacking_side]
    goal_players = targets[attacking_side]["GOAL"][attacking_side]

    assert sum(in_final_third(marker["x"]) for marker in chance_players) >= 6
    assert sum(near_goal(marker["x"]) for marker in goal_players) >= 3


def _selected_session(seed: int, side: TeamSide = TeamSide.TEAM_A) -> WebMatchSession:
    session = WebMatchSession(seed=seed, api_key="", model="")
    session.select_team(side)
    session.set_human_tactic(TeamTactic.BALANCED)
    return session


@pytest.mark.parametrize("side", [TeamSide.TEAM_A, TeamSide.TEAM_B])
def test_playback_visual_contract_supports_both_human_team_selections(
    side: TeamSide,
) -> None:
    response = _selected_session(91, side).start()

    assert response["team_selection"]["selected_side"] == side.value
    assert response["visualizer"]["teams"]["team_a"]["name"] == "AI United"
    assert response["visualizer"]["teams"]["team_b"]["name"] == "Neural FC"
    assert response["visualizer"]["schema_version"] == 1
    assert response["playback"]["timeline"]
    assert all(
        set(event["visual"]) == {"mode", "attacking_side"}
        for event in response["playback"]["timeline"]
    )


def test_reading_visualizer_payload_does_not_change_resolved_match() -> None:
    baseline = _selected_session(92)
    observed = _selected_session(92)

    for _ in range(3):
        payload = observed.state_payload()["visualizer"]
        assert payload["frame"]["mode"] == "NEUTRAL"

    baseline_response = baseline.start()
    observed_response = observed.start()

    assert observed.controller.state == baseline.controller.state
    assert observed_response["score"] == baseline_response["score"]
    assert (
        observed_response["playback"]["final_score"]
        == baseline_response["playback"]["final_score"]
    )


def test_visualizer_assets_are_isolated_and_served() -> None:
    client = TestClient(create_app(WebMatchSession(seed=93, api_key="", model="")))

    page = client.get("/")
    script = client.get("/static/js/match-visualizer.js")
    stylesheet = client.get("/static/css/match-visualizer.css")

    assert page.status_code == 200
    management_markup, match_center_markup = page.text.split("</main>", 1)
    assert 'id="match-visualizer"' not in management_markup
    assert match_center_markup.count('id="match-visualizer"') == 1
    assert page.text.index('id="match-center"') < page.text.index('id="match-visualizer"')
    assert 'id="match-center" class="match-center" role="dialog"' in page.text
    assert 'class="visual-pitch-frame"' in page.text
    assert 'preserveAspectRatio="xMidYMid meet"' in page.text
    assert '<div class="visual-pitch-frame" hidden' not in page.text
    assert "/static/js/match-visualizer.js" in page.text
    assert "/static/css/match-visualizer.css" in page.text
    assert script.status_code == 200
    assert "class MatchVisualizer" in script.text
    assert stylesheet.status_code == 200
    assert ".match-visualizer" in stylesheet.text
    assert ".visual-pitch-frame" in stylesheet.text
    assert "animationTargets" in script.text
    assert "document.body" not in script.text


def test_responsive_shell_keeps_required_gameplay_controls() -> None:
    client = TestClient(create_app(WebMatchSession(seed=94, api_key="", model="")))

    page = client.get("/").text
    app_script = client.get("/static/js/app.js").text
    stylesheet = client.get("/static/css/app.css").text

    assert 'class="match-footer"' in page
    assert 'class="command-grid"' in page
    assert 'id="event-list"' in page
    assert 'id="assistant-recommendation"' in page
    assert 'id="match-action"' in page
    assert 'id="pause-at-breaks"' in page
    assert 'data-tactic="ATTACK"' in page
    assert 'data-tactic="BALANCED"' in page
    assert 'data-tactic="DEFEND"' in page
    assert 'classList.toggle("match-live"' in app_script
    assert ".match-center-surface" in stylesheet
    assert ".match-center[hidden]" in stylesheet
    assert ".match-sidebars { grid-template-columns: 1fr;" in stylesheet


def test_laptop_layout_prioritizes_field_without_changing_large_layout() -> None:
    client = TestClient(create_app(WebMatchSession(seed=95, api_key="", model="")))

    page = client.get("/").text
    stylesheet = client.get("/static/css/app.css").text
    visualizer_stylesheet = client.get(
        "/static/css/match-visualizer.css"
    ).text

    assert 'class="gameplay-grid"' in page
    assert 'id="match-visualizer"' in page
    assert 'class="match-sidebars"' in page
    assert 'id="event-list"' in page
    assert 'id="decision-list"' in page
    assert 'id="manager-controls"' in page
    assert 'id="match-action"' in page
    assert "Laptop layout: protect the field" in stylesheet
    assert ".gameplay-grid { display: grid; grid-template-columns:" in stylesheet
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);" in stylesheet
    assert "grid-template-rows: auto auto" in stylesheet
    assert "overflow-y: auto" in stylesheet
    assert ".management-start { grid-column: 1 / -1; }" in stylesheet
    assert ".command-grid { grid-template-columns: minmax(0, 1fr); }" in stylesheet
    assert ".visual-pitch-frame" in visualizer_stylesheet
    assert "aspect-ratio: 5 / 3" in visualizer_stylesheet
    assert "max-width: 100%" in visualizer_stylesheet
    assert "max-height: none" in visualizer_stylesheet
    assert "max-height: 100%" not in visualizer_stylesheet
    assert "height: auto" in visualizer_stylesheet


def test_short_desktop_uses_compact_height_aware_match_center_geometry() -> None:
    client = TestClient(create_app(WebMatchSession(seed=96, api_key="", model="")))

    page = client.get("/").text
    stylesheet = client.get("/static/css/app.css").text
    visualizer_stylesheet = client.get(
        "/static/css/match-visualizer.css"
    ).text

    assert 'id="match-center" class="match-center"' in page
    assert 'id="match-visualizer"' in page
    assert 'id="event-list"' in page
    assert 'id="decision-list"' in page
    assert 'id="match-action"' in page
    assert "Compact Match Center: use height" in stylesheet
    assert "@media (min-width: 901px) and (max-height:" in stylesheet
    assert "grid-template-columns: minmax(0, 3fr) minmax(300px, 1fr);" in stylesheet
    assert "grid-template-rows: auto minmax(0, 1fr) auto;" in stylesheet
    assert "Compact Match Center: the pitch frame follows" in visualizer_stylesheet
    assert ".visual-pitch-frame" in visualizer_stylesheet
    assert "height: 100%;" in visualizer_stylesheet
    assert "aspect-ratio: 5 / 3;" in visualizer_stylesheet
