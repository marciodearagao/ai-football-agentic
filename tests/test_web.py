import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.web.session import WebMatchSession


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    application = create_app(WebMatchSession(seed=42))
    return TestClient(application)


def test_index_succeeds(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "AI Football Agentic" in response.text
    assert "Match Lab · v0.1.0" in response.text
    assert "Season Lab" not in response.text
    assert 'id="pause-at-breaks" type="checkbox" checked' in response.text
    assert 'id="manage-team"' in response.text
    assert "disabled" in response.text


def test_loading_label_describes_match_preparation(client: TestClient) -> None:
    response = client.get("/static/js/app.js")

    assert response.status_code == 200
    assert "PREPARING MATCH…" in response.text
    assert "CALCULATING…" not in response.text


def test_initial_state_is_available(client: TestClient) -> None:
    state = client.get("/api/match/state").json()

    assert state["phase"] == "NOT_STARTED"
    assert state["completed_blocks"] == 0
    assert state["team_a"]["name"] == "AI United"
    assert state["team_b"]["name"] == "Neural FC"
    assert state["can_start"] is True
    assert state["usage"]["calls"] == 0
    assert state["groq_status"] == "NOT_CONFIGURED"
    assert state["display_clock"] == "0'"
    assert state["presentation_feed"] == []
    assert state["playback"] is None


def test_start_simulates_exactly_one_block(client: TestClient) -> None:
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
    assert "BLOCK 1 IN PROGRESS" not in json.dumps(state).upper()


def test_continue_advances_exactly_one_block(client: TestClient) -> None:
    client.post("/api/match/start")

    state = client.post("/api/match/continue").json()

    assert state["completed_blocks"] == 2
    assert state["phase"] == "HALF_TIME"
    assert state["display_period"] == "Half-time — 45+5'"


def test_break_labels_and_full_time_auto_resume_state_are_unchanged(
    client: TestClient,
) -> None:
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
    assert "localStorage" not in script


def test_invalid_continue_is_rejected_without_internal_error(client: TestClient) -> None:
    response = client.post("/api/match/continue")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "The match cannot continue from phase NOT_STARTED."
    )


def test_complete_no_groq_flow_stops_at_full_time_and_resets(client: TestClient) -> None:
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


def test_state_contains_usage_but_no_raw_provider_data(client: TestClient) -> None:
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
