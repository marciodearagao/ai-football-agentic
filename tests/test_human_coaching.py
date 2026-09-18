import json
from types import SimpleNamespace

import pytest

from app.agents.assistant import AssistantCoach
from app.domain.enums import MatchPhase, TeamTactic
from app.web.session import TeamSide, WebMatchSession


@pytest.mark.parametrize(
    (
        "side",
        "human_team_attribute",
        "human_coach_attribute",
        "opponent_coach_attribute",
    ),
    [
        (TeamSide.TEAM_A, "team_a", "team_a_coach", "team_b_coach"),
        (TeamSide.TEAM_B, "team_b", "team_b_coach", "team_a_coach"),
    ],
)
def test_human_manager_controls_selected_team_and_opponent_coach_stays_autonomous(
    side: TeamSide,
    human_team_attribute: str,
    human_coach_attribute: str,
    opponent_coach_attribute: str,
) -> None:
    session = WebMatchSession(seed=44, api_key="", model="")
    session.select_team(side)
    session.set_human_tactic(TeamTactic.ATTACK)

    response = session.start()

    human_team = getattr(session.controller, human_team_attribute)
    human_coach = getattr(session.controller, human_coach_attribute)
    opponent_coach = getattr(session.controller, opponent_coach_attribute)
    assert human_team.tactic is TeamTactic.ATTACK
    assert human_coach.decision_count == 0
    assert opponent_coach.decision_count == 1
    assert response["human_manager"]["tactic"] == "ATTACK"


def test_assistant_recommendation_never_mutates_team_tactic() -> None:
    def recommend_attack(**_):
        return SimpleNamespace(
            id="assistant-response",
            model="test-model",
            usage=None,
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "tactic": "ATTACK",
                                "reason": "Increase the pressure.",
                            }
                        )
                    )
                )
            ],
        )

    session = WebMatchSession(seed=45, api_key="", model="")
    assistant = AssistantCoach(
        "AI United",
        model="test-model",
        completion_create=recommend_attack,
    )

    recommendation = session.controller.request_assistant_recommendation(
        assistant,
        is_team_a=True,
        phase=MatchPhase.FIRST_BLOCK,
    )

    assert recommendation.tactic is TeamTactic.ATTACK
    assert session.controller.team_a.tactic is TeamTactic.BALANCED
    assert session.controller.state.team_a_tactic is TeamTactic.BALANCED


def test_human_manager_tactic_reaches_match_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = WebMatchSession(seed=46, api_key="", model="")
    session.select_team(TeamSide.TEAM_A)
    session.set_human_tactic(TeamTactic.DEFEND)
    observed: dict[str, TeamTactic] = {}
    evaluate_block = session.controller._engine.evaluate_block

    def capture_tactics(team_a, team_b):
        observed["team_a"] = team_a.tactic
        observed["team_b"] = team_b.tactic
        return evaluate_block(team_a, team_b)

    monkeypatch.setattr(session.controller._engine, "evaluate_block", capture_tactics)

    session.start()

    assert observed["team_a"] is TeamTactic.DEFEND
    assert session.controller.team_a_coach.decision_count == 0
    assert session.controller.team_b_coach.decision_count == 1


def test_human_manager_can_change_tactic_before_the_next_block() -> None:
    session = WebMatchSession(seed=47, api_key="", model="")
    session.select_team(TeamSide.TEAM_B)
    session.set_human_tactic(TeamTactic.ATTACK)
    session.start()

    session.set_human_tactic(TeamTactic.DEFEND)
    response = session.continue_match()

    assert session.controller.team_b.tactic is TeamTactic.DEFEND
    assert response["human_manager"]["tactic"] == "DEFEND"
    assert session.controller.team_b_coach.decision_count == 0
    assert session.controller.team_a_coach.decision_count == 2
