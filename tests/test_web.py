import json
from pathlib import Path
import tomllib

import pytest
from fastapi.testclient import TestClient

from app.domain.enums import TeamTactic
from app.main import create_app
from app.version import APP_VERSION
from app.web.session import TeamSide, WebMatchSession
from run import APP_VERSION as LAUNCHER_VERSION


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    application = create_app(WebMatchSession(seed=42, api_key="", model=""))
    return TestClient(application)


def _select_team(client: TestClient, side: str = "team_a") -> dict[str, object]:
    response = client.post("/api/match/select-team", json={"side": side})
    assert response.status_code == 200
    return response.json()


def _select_tactic(
    client: TestClient,
    tactic: str = "BALANCED",
) -> dict[str, object]:
    response = client.post("/api/match/human-tactic", json={"tactic": tactic})
    assert response.status_code == 200
    return response.json()


def test_index_succeeds(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "AI Football Agentic" in response.text
    assert APP_VERSION == "0.2.0"
    assert "Match Lab · v0.2.0" in response.text
    assert "Match Lab · v0.1.0" not in response.text
    assert client.app.version == APP_VERSION
    assert "Season Lab" not in response.text
    assert 'id="pause-at-breaks" type="checkbox" checked' in response.text
    assert 'id="team-selection"' in response.text
    assert 'class="management-summary"' in response.text
    assert 'id="setup-action"' in response.text
    assert 'id="match-center" class="match-center" role="dialog"' in response.text
    assert 'aria-hidden="true" hidden' in response.text
    assert 'id="manager-controls"' in response.text
    assert "Choose Your Team" in response.text
    assert "Your Team" in response.text
    assert 'data-tactic="ATTACK"' in response.text
    assert 'data-tactic="BALANCED"' in response.text
    assert 'data-tactic="DEFEND"' in response.text
    assert "disabled" in response.text


def test_release_version_is_consistent_across_runtime_metadata(
    client: TestClient,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((project_root / "pyproject.toml").read_text())

    assert APP_VERSION == "0.2.0"
    assert LAUNCHER_VERSION == APP_VERSION
    assert metadata["project"]["version"] == APP_VERSION
    assert client.get("/openapi.json").json()["info"]["version"] == APP_VERSION


def test_loading_label_describes_match_preparation(client: TestClient) -> None:
    response = client.get("/static/js/app.js")

    assert response.status_code == 200
    assert "PREPARING MATCH…" in response.text
    assert "CALCULATING…" not in response.text
    assert 'fetchJson("/api/match/select-team"' in response.text
    assert 'fetchJson("/api/match/human-tactic"' in response.text
    assert '"Your Team"' in response.text
    assert '"Opponent"' in response.text
    assert "AI Assistant recommends" in response.text


def test_initial_state_is_available(client: TestClient) -> None:
    state = client.get("/api/match/state").json()

    assert state["phase"] == "NOT_STARTED"
    assert state["completed_blocks"] == 0
    assert state["team_a"]["name"] == "AI United"
    assert state["team_b"]["name"] == "Neural FC"
    assert state["can_start"] is False
    assert state["team_selection"]["required"] is True
    assert state["team_selection"]["selected_side"] is None
    assert state["team_selection"]["your_team"] is None
    assert state["team_selection"]["opponent"] is None
    assert state["human_manager"] == {
        "team_side": None,
        "tactic": None,
        "can_choose_tactic": False,
    }
    assert state["assistant_recommendation"] is None
    assert [team["name"] for team in state["team_selection"]["options"]] == [
        "AI United",
        "Neural FC",
    ]
    assert state["usage"]["calls"] == 0
    assert state["provider_status"] == {
        "provider": "FALLBACK",
        "state": "DETERMINISTIC",
    }
    assert state["display_clock"] == "0'"
    assert state["presentation_feed"] == []
    assert state["playback"] is None
    assert state["presentation_started"] is False
    assert state["visualizer"]["schema_version"] == 1
    assert state["visualizer"]["teams"] == {
        "team_a": {"name": "AI United"},
        "team_b": {"name": "Neural FC"},
    }
    assert state["visualizer"]["frame"] == {
        "mode": "NEUTRAL",
        "attacking_side": None,
    }
    assert len(state["visualizer"]["formations"]["team_a"]) == 11
    assert len(state["visualizer"]["formations"]["team_b"]) == 11


@pytest.mark.parametrize(
    ("side", "your_team", "opponent"),
    [
        ("team_a", "AI United", "Neural FC"),
        ("team_b", "Neural FC", "AI United"),
    ],
)
def test_selecting_team_assigns_human_team_and_opponent(
    client: TestClient,
    side: str,
    your_team: str,
    opponent: str,
) -> None:
    state = _select_team(client, side)

    assert state["team_selection"]["required"] is False
    assert state["team_selection"]["selected_side"] == side
    assert state["team_selection"]["your_team"]["name"] == your_team
    assert state["team_selection"]["opponent"]["name"] == opponent
    assert state["human_manager"]["team_side"] == side
    assert state["human_manager"]["tactic"] is None
    assert state["assistant_recommendation"]["tactic"] == "BALANCED"
    assert state["can_start"] is False


def test_match_cannot_start_before_team_selection(client: TestClient) -> None:
    response = client.post("/api/match/start")

    assert response.status_code == 409
    assert response.json()["detail"] == "Select a team before starting the match."


def test_match_cannot_start_before_human_tactic(client: TestClient) -> None:
    _select_team(client)

    response = client.post("/api/match/start")

    assert response.status_code == 409
    assert response.json()["detail"] == "Choose a tactic before starting the match."


def test_start_simulates_exactly_one_block(client: TestClient) -> None:
    _select_team(client)
    _select_tactic(client)
    state = client.post("/api/match/start").json()

    assert state["completed_blocks"] == 1
    assert state["phase"] == "FIRST_HYDRATION"
    assert state["display_period"] == "Hydration Break — 25'"
    assert state["can_continue"] is True
    assert state["playback"]["block_number"] == 1
    assert len(state["playback"]["clocks"]) == 25
    assert state["playback"]["start_score"] == {"team_a": 0, "team_b": 0}
    assert state["playback"]["final_score"] == state["score"]
    assert state["playback"]["status_label"] == "MATCH IN PROGRESS"
    assert state["presentation_started"] is True
    assert all("visual" in event for event in state["playback"]["timeline"])
    assert "BLOCK 1 IN PROGRESS" not in json.dumps(state).upper()
    assert state["team_selection"]["selected_side"] == "team_a"


def test_continue_advances_exactly_one_block(client: TestClient) -> None:
    _select_team(client)
    _select_tactic(client)
    client.post("/api/match/start")

    state = client.post("/api/match/continue").json()

    assert state["completed_blocks"] == 2
    assert state["phase"] == "HALF_TIME"
    assert state["display_period"] == "Half-time — 45+5'"


def test_break_labels_and_full_time_auto_resume_state_are_unchanged(
    client: TestClient,
) -> None:
    _select_team(client)
    _select_tactic(client)
    first_break = client.post("/api/match/start").json()
    half_time = client.post("/api/match/continue").json()
    second_break = client.post("/api/match/continue").json()
    full_time = client.post("/api/match/continue").json()

    assert first_break["display_period"] == "Hydration Break — 25'"
    assert half_time["display_period"] == "Half-time — 45+5'"
    assert second_break["display_period"] == "Hydration Break — 70'"
    assert full_time["display_period"] == "Full Time — 90+5'"
    assert full_time["can_continue"] is False
    assert full_time["is_full_time"] is True


def test_browser_break_controls_are_client_only(client: TestClient) -> None:
    script = client.get("/static/js/app.js").text

    assert "const AUTO_BREAK_SECONDS = 15" in script
    assert "pauseAtBreaks.checked" in script
    assert 'runMatchAction("/api/match/continue")' in script
    assert "currentState.is_full_time" in script


def test_management_and_match_center_have_stable_separate_structures(
    client: TestClient,
) -> None:
    page = client.get("/").text
    script = client.get("/static/js/app.js").text
    stylesheet = client.get("/static/css/app.css").text

    assert '<body class="match-setup">' in page
    assert 'id="team-selection"' in page
    assert 'class="management-summary"' in page
    assert 'id="setup-action"' in page
    assert 'id="match-center" class="match-center" role="dialog"' in page
    assert page.index('id="match-center"') < page.index('id="match-visualizer"')
    assert 'id="manager-controls"' in page
    assert 'id="match-action"' in page
    assert 'id="break-countdown" class="break-countdown"' in page
    assert "for (const controls of elements.managerControls)" in script
    assert ".match-center[hidden]" in stylesheet
    assert ".match-center-surface" in stylesheet
    assert "grid-template-rows: auto minmax(0, 1fr) auto" in stylesheet
    assert ".break-countdown.is-active" in stylesheet


def test_match_center_mode_tracks_match_lifecycle_without_gameplay_mutation(
    client: TestClient,
) -> None:
    script = client.get("/static/js/app.js").text

    assert 'const open = playing || state.phase !== "NOT_STARTED"' in script
    assert "elements.matchCenter.hidden = !open" in script
    assert "elements.gameShell.inert = open" in script
    assert 'classList.toggle("match-center-open", open)' in script
    assert '"NEW MATCH · EXIT MATCH CENTER"' in script
    assert 'elements.setupAction.dataset.endpoint = "/api/match/start"' in script
    assert 'elements.action.dataset.endpoint = "/api/match/reset"' in script

    initial = client.get("/api/match/state").json()
    assert initial["phase"] == "NOT_STARTED"
    assert initial["completed_blocks"] == 0

    _select_team(client)
    _select_tactic(client)
    hydration = client.post("/api/match/start").json()
    half_time = client.post("/api/match/continue").json()

    assert hydration["phase"] == "FIRST_HYDRATION"
    assert half_time["phase"] == "HALF_TIME"
    assert hydration["completed_blocks"] == 1
    assert half_time["completed_blocks"] == 2


def test_configured_provider_is_ready_before_any_inference() -> None:
    session = WebMatchSession(seed=48, api_key="test-key", model="test-model")

    assert session.state_payload()["provider_status"] == {
        "provider": "GROQ",
        "state": "READY",
    }


def test_gemini_key_uses_default_model_and_is_ready_without_groq() -> None:
    session = WebMatchSession(
        seed=49,
        api_key="",
        model="",
        gemini_api_key="test-gemini-key",
        gemini_model=None,
    )

    assert session.controller.team_a_coach.gemini_model == "gemini-3.1-flash-lite"
    assert session.state_payload()["provider_status"] == {
        "provider": "GEMINI",
        "state": "READY",
    }


def test_match_event_empty_message_tracks_presentation_state(
    client: TestClient,
) -> None:
    script = client.get("/static/js/app.js").text

    assert "playing || state.presentation_started" in script
    assert "The match has not started." in script
    assert "Match underway. Waiting for the next event." in script
    assert "localStorage" not in script


def test_invalid_continue_is_rejected_without_internal_error(
    client: TestClient,
) -> None:
    response = client.post("/api/match/continue")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "The match cannot continue from phase NOT_STARTED."
    )


def test_complete_no_groq_flow_stops_at_full_time_and_resets(
    client: TestClient,
) -> None:
    _select_team(client)
    _select_tactic(client)
    state = client.post("/api/match/start").json()
    for expected_blocks in (2, 3, 4):
        state = client.post("/api/match/continue").json()
        assert state["completed_blocks"] == expected_blocks

    assert state["phase"] == "FULL_TIME"
    assert state["is_full_time"] is True
    assert state["usage"]["calls"] == 0
    assert client.post("/api/match/continue").status_code == 409

    fresh = client.post("/api/match/reset").json()
    assert fresh["phase"] == "NOT_STARTED"
    assert fresh["completed_blocks"] == 0
    assert fresh["score"] == {"team_a": 0, "team_b": 0}
    assert fresh["team_a"]["average_energy"] == 100.0
    assert fresh["team_b"]["average_energy"] == 100.0
    assert fresh["team_selection"]["required"] is True
    assert fresh["team_selection"]["selected_side"] is None
    assert fresh["human_manager"]["tactic"] is None
    assert fresh["assistant_recommendation"] is None
    assert fresh["can_start"] is False


def test_state_contains_usage_but_no_raw_provider_data(client: TestClient) -> None:
    _select_team(client)
    _select_tactic(client)
    state = client.post("/api/match/start").json()
    serialized = json.dumps(state).lower()

    assert set(state["usage"]) == {
        "calls",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_tokens",
        "estimated_cost",
    }
    assert "response_metadata" not in serialized
    assert "api_key" not in serialized
    assert "system_prompt" not in serialized
    assert "provider_error" not in serialized
    assert set(state["assistant_recommendation"]) == {"tactic"}


def test_selection_does_not_change_seeded_match_behavior() -> None:
    human_team_a = WebMatchSession(seed=42, api_key="", model="")
    human_team_b = WebMatchSession(seed=42, api_key="", model="")
    human_team_a.select_team(TeamSide.TEAM_A)
    human_team_b.select_team(TeamSide.TEAM_B)
    human_team_a.set_human_tactic(TeamTactic.BALANCED)
    human_team_b.set_human_tactic(TeamTactic.BALANCED)

    first = human_team_a.start()
    second = human_team_b.start()

    assert first["score"] == second["score"]
    assert first["events"] == second["events"]
    assert human_team_a.controller.state == human_team_b.controller.state
    assert (
        human_team_a.controller.completed_blocks[0].simulation
        == human_team_b.controller.completed_blocks[0].simulation
    )
