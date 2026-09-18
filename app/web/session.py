import os
import secrets
from decimal import Decimal
from enum import StrEnum
from threading import Lock
from typing import Any

from app.agents.assistant import AssistantCoach
from app.agents.coach import CoachAgent, CoachDecision
from app.domain.enums import MatchPhase, TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.footballers.cognitive import CognitiveFootballer
from app.footballers.reactive import ReactiveFootballer
from app.footballers.tactical import TacticalFootballer
from app.match.match_controller import InvalidMatchTransition, MatchController
from app.match.phases import MATCH_BLOCKS
from app.web.presentation import BlockPlayback, build_block_playback
from app.web.visualizer import visual_state_for_event, visualizer_payload


PHASE_LABELS = {
    MatchPhase.NOT_STARTED: "Ready for kickoff",
    MatchPhase.FIRST_HYDRATION: "Hydration Break — 25'",
    MatchPhase.HALF_TIME: "Half-time — 45+5'",
    MatchPhase.SECOND_HYDRATION: "Hydration Break — 70'",
    MatchPhase.FULL_TIME: "Full Time — 90+5'",
}

PROGRESS_BY_PHASE = {
    MatchPhase.NOT_STARTED: 0,
    MatchPhase.FIRST_HYDRATION: 25,
    MatchPhase.HALF_TIME: 50,
    MatchPhase.SECOND_HYDRATION: 75,
    MatchPhase.FULL_TIME: 100,
}


class TeamSide(StrEnum):
    TEAM_A = "team_a"
    TEAM_B = "team_b"


class WebMatchSession:
    """Own the single local match exposed by the browser application."""

    def __init__(
        self,
        *,
        seed: int | None = None,
        api_key: str | None = None,
        model: str | None = None,
        gemini_api_key: str | None = None,
        gemini_model: str | None = None,
    ) -> None:
        self._fixed_seed = seed
        configured_api_key = (
            api_key if api_key is not None else os.getenv("GROQ_API_KEY")
        )
        configured_model = model if model is not None else os.getenv("GROQ_MODEL")
        self._api_key = configured_api_key or ""
        self._model = configured_model or ""
        configured_gemini_api_key = (
            gemini_api_key
            if gemini_api_key is not None
            else os.getenv("GEMINI_API_KEY")
        )
        configured_gemini_model = (
            gemini_model
            if gemini_model is not None
            else os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        )
        self._gemini_api_key = configured_gemini_api_key or ""
        self._gemini_model = configured_gemini_model or ""
        self._lock = Lock()
        self._create_match()

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self.selected_side is None:
                raise InvalidMatchTransition(
                    "Select a team before starting the match."
                )
            if self.human_tactic is None:
                raise InvalidMatchTransition(
                    "Choose a tactic before starting the match."
                )
            playback = self._simulate_for_playback(start=True)
            return self._state_payload(playback)

    def select_team(self, side: TeamSide) -> dict[str, Any]:
        with self._lock:
            if self.controller.phase is not MatchPhase.NOT_STARTED:
                raise InvalidMatchTransition(
                    "Team selection is available only before the match starts."
                )
            self.selected_side = side
            self.human_tactic = None
            team = (
                self.controller.team_a
                if side is TeamSide.TEAM_A
                else self.controller.team_b
            )
            self.assistant_coach = AssistantCoach(
                team.name,
                api_key=self._api_key,
                model=self._model,
                gemini_api_key=self._gemini_api_key,
                gemini_model=self._gemini_model,
            )
            self._refresh_assistant_recommendation()
            return self._state_payload()

    def set_human_tactic(self, tactic: TeamTactic) -> dict[str, Any]:
        with self._lock:
            if self.selected_side is None:
                raise InvalidMatchTransition(
                    "Select a team before choosing a tactic."
                )
            if self.controller.phase not in {
                MatchPhase.NOT_STARTED,
                MatchPhase.FIRST_HYDRATION,
                MatchPhase.HALF_TIME,
                MatchPhase.SECOND_HYDRATION,
            }:
                raise InvalidMatchTransition(
                    "The Human Manager cannot change tactic in the current phase."
                )
            self.human_tactic = tactic
            return self._state_payload()

    def continue_match(self) -> dict[str, Any]:
        with self._lock:
            if self.controller.phase not in {
                MatchPhase.FIRST_HYDRATION,
                MatchPhase.HALF_TIME,
                MatchPhase.SECOND_HYDRATION,
            }:
                phase = self.controller.phase.value
                raise InvalidMatchTransition(
                    f"The match cannot continue from phase {phase}."
                )
            playback = self._simulate_for_playback(start=False)
            return self._state_payload(playback)

    def reset(self) -> dict[str, Any]:
        with self._lock:
            if self.controller.phase is not MatchPhase.FULL_TIME:
                raise InvalidMatchTransition(
                    "A new match is available only after full time."
                )
            self._create_match()
            return self._state_payload()

    def state_payload(self) -> dict[str, Any]:
        with self._lock:
            return self._state_payload()

    def _create_match(self) -> None:
        self.match_seed = (
            self._fixed_seed
            if self._fixed_seed is not None
            else secrets.randbits(63)
        )
        self._presentation_blocks: list[BlockPlayback] = []
        self.selected_side: TeamSide | None = None
        self.human_tactic: TeamTactic | None = None
        self.assistant_coach: AssistantCoach | None = None
        self.assistant_recommendation: CoachDecision | None = None
        self._latest_ai_agent: Any | None = None
        team_a = _create_team("AI United", skill=78, stamina=78)
        team_b = _create_team("Neural FC", skill=76, stamina=80)
        team_a_makers, self._team_a_cognitive = _create_decision_makers(
            team_a,
            api_key=self._api_key,
            model=self._model,
        )
        team_b_makers, self._team_b_cognitive = _create_decision_makers(
            team_b,
            api_key=self._api_key,
            model=self._model,
        )
        self.controller = MatchController(
            team_a,
            team_b,
            team_a_makers,
            team_b_makers,
            seed=self.match_seed,
            team_a_coach=CoachAgent(
                team_a.name,
                api_key=self._api_key,
                model=self._model,
                gemini_api_key=self._gemini_api_key,
                gemini_model=self._gemini_model,
            ),
            team_b_coach=CoachAgent(
                team_b.name,
                api_key=self._api_key,
                model=self._model,
                gemini_api_key=self._gemini_api_key,
                gemini_model=self._gemini_model,
            ),
        )

    def _simulate_for_playback(self, *, start: bool) -> BlockPlayback:
        if self.selected_side is None or self.human_tactic is None:
            raise InvalidMatchTransition(
                "A selected team and Human Manager tactic are required."
            )
        state = self.controller.state
        start_score = (state.team_a_score, state.team_b_score)
        start_energy = (
            state.team_a_average_energy,
            state.team_b_average_energy,
        )
        tactic_arguments = {
            "team_a_tactic": (
                self.human_tactic
                if self.selected_side is TeamSide.TEAM_A
                else None
            ),
            "team_b_tactic": (
                self.human_tactic
                if self.selected_side is TeamSide.TEAM_B
                else None
            ),
        }
        block = (
            self.controller.start(**tactic_arguments)
            if start
            else self.controller.continue_match(**tactic_arguments)
        )
        # Team B's cognitive decision is the final AI decision inside a block.
        # A following Assistant Coach recommendation supersedes it below.
        self._latest_ai_agent = self._team_b_cognitive
        playback = build_block_playback(
            block,
            block_number=len(self.controller.completed_blocks),
            match_seed=self.match_seed,
            team_a_name=self.controller.team_a.name,
            team_b_name=self.controller.team_b.name,
            start_score=start_score,
            start_energy=start_energy,
            last_activity_minute=(
                self._presentation_blocks[-1].timeline[-1].absolute_minute
                if self._presentation_blocks
                and self._presentation_blocks[-1].timeline
                else 0
            ),
            last_narrative_text=self._last_narrative_text(),
        )
        self._presentation_blocks.append(playback)
        self._refresh_assistant_recommendation()
        return playback

    def _refresh_assistant_recommendation(self) -> None:
        if (
            self.selected_side is None
            or self.assistant_coach is None
            or len(self.controller.completed_blocks) >= len(MATCH_BLOCKS)
        ):
            self.assistant_recommendation = None
            return
        next_block = MATCH_BLOCKS[len(self.controller.completed_blocks)]
        self.assistant_recommendation = (
            self.controller.request_assistant_recommendation(
                self.assistant_coach,
                is_team_a=self.selected_side is TeamSide.TEAM_A,
                phase=next_block.phase,
            )
        )
        self._latest_ai_agent = self.assistant_coach

    def _last_narrative_text(self) -> str | None:
        for playback in reversed(self._presentation_blocks):
            for event in reversed(playback.timeline):
                if event.kind == "PRESENTATION" and event.type not in {
                    "QUIET_MATCH",
                    "MILESTONE",
                }:
                    return event.text
        return None

    def _state_payload(
        self,
        playback: BlockPlayback | None = None,
    ) -> dict[str, Any]:
        controller = self.controller
        state = controller.state
        blocks = controller.completed_blocks
        latest_block = blocks[-1] if blocks else None
        events = [event for block in blocks for event in block.events]
        usage = controller.usage_tracker.match_totals()
        can_continue = self.human_tactic is not None and state.phase in {
            MatchPhase.FIRST_HYDRATION,
            MatchPhase.HALF_TIME,
            MatchPhase.SECOND_HYDRATION,
        }
        team_selection = self._team_selection_payload()

        return {
            "phase": state.phase.value,
            "display_period": PHASE_LABELS[state.phase],
            "display_clock": (
                self._presentation_blocks[-1].clocks[-1]
                if self._presentation_blocks
                else "0'"
            ),
            "completed_blocks": len(blocks),
            "presentation_started": bool(blocks),
            "progress_percent": PROGRESS_BY_PHASE[state.phase],
            "team_a": _team_payload(controller.team_a, state.team_a_average_energy),
            "team_b": _team_payload(controller.team_b, state.team_b_average_energy),
            "team_selection": team_selection,
            "human_manager": self._human_manager_payload(),
            "assistant_recommendation": (
                {
                    "tactic": self.assistant_recommendation.tactic.value,
                }
                if self.assistant_recommendation
                else None
            ),
            "score": {
                "team_a": state.team_a_score,
                "team_b": state.team_b_score,
            },
            "visualizer": visualizer_payload(
                controller.team_a.name,
                controller.team_b.name,
            ),
            "events": [
                {
                    "type": event.type.value,
                    "team_name": event.team_name,
                    "footballer_name": event.footballer_name,
                    "display_minute": event.display_minute,
                    "previous_tactic": (
                        event.previous_tactic.value if event.previous_tactic else None
                    ),
                    "new_tactic": event.new_tactic.value if event.new_tactic else None,
                }
                for event in events
            ],
            "presentation_feed": [
                _timeline_event_payload(event)
                for block_playback in self._presentation_blocks
                for event in block_playback.timeline
            ],
            "playback": _playback_payload(playback) if playback else None,
            "coach_decisions": (
                {
                    "team_a": {
                        "team_name": controller.team_a.name,
                        "tactic": latest_block.team_a_coach_decision.tactic.value,
                        "role": (
                            "Human Manager"
                            if self.selected_side is TeamSide.TEAM_A
                            else "Opponent Coach"
                        ),
                    },
                    "team_b": {
                        "team_name": controller.team_b.name,
                        "tactic": latest_block.team_b_coach_decision.tactic.value,
                        "role": (
                            "Human Manager"
                            if self.selected_side is TeamSide.TEAM_B
                            else "Opponent Coach"
                        ),
                    },
                }
                if latest_block
                else None
            ),
            "footballer_decisions": (
                {
                    "team_a": {
                        "footballer_name": self._team_a_cognitive.footballer_name,
                        "behavior": controller.team_a.footballers[0].behavior.value,
                    },
                    "team_b": {
                        "footballer_name": self._team_b_cognitive.footballer_name,
                        "behavior": controller.team_b.footballers[0].behavior.value,
                    },
                }
                if latest_block
                else None
            ),
            "usage": {
                "calls": usage.calls,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
                "cached_tokens": usage.cached_tokens,
                "estimated_cost": _cost_value(usage.estimated_cost),
            },
            "provider_status": self._provider_status_payload(),
            "can_start": (
                state.phase is MatchPhase.NOT_STARTED
                and self.selected_side is not None
                and self.human_tactic is not None
            ),
            "can_continue": can_continue,
            "is_full_time": state.phase is MatchPhase.FULL_TIME,
        }

    def _human_manager_payload(self) -> dict[str, Any]:
        if self.selected_side is None:
            return {
                "team_side": None,
                "tactic": None,
                "can_choose_tactic": False,
            }
        return {
            "team_side": self.selected_side.value,
            "tactic": self.human_tactic.value if self.human_tactic else None,
            "can_choose_tactic": self.controller.phase in {
                MatchPhase.NOT_STARTED,
                MatchPhase.FIRST_HYDRATION,
                MatchPhase.HALF_TIME,
                MatchPhase.SECOND_HYDRATION,
            },
        }

    def _team_selection_payload(self) -> dict[str, Any]:
        teams = {
            TeamSide.TEAM_A: self.controller.team_a,
            TeamSide.TEAM_B: self.controller.team_b,
        }
        options = [
            {
                "side": side.value,
                "name": team.name,
                "squad_size": len(team.footballers),
                "base_strength": round(team.base_strength, 1),
            }
            for side, team in teams.items()
        ]
        if self.selected_side is None:
            return {
                "required": True,
                "selected_side": None,
                "your_team": None,
                "opponent": None,
                "options": options,
            }

        opponent_side = (
            TeamSide.TEAM_B
            if self.selected_side is TeamSide.TEAM_A
            else TeamSide.TEAM_A
        )
        return {
            "required": False,
            "selected_side": self.selected_side.value,
            "your_team": {
                "side": self.selected_side.value,
                "name": teams[self.selected_side].name,
            },
            "opponent": {
                "side": opponent_side.value,
                "name": teams[opponent_side].name,
            },
            "options": options,
        }

    def _provider_status_payload(self) -> dict[str, str]:
        """Describe configuration or the latest AI execution without error detail."""
        agent = self._latest_ai_agent
        if agent is not None:
            successful_provider = getattr(agent, "last_successful_provider", None)
            if successful_provider is not None:
                return {
                    "provider": successful_provider.value.upper(),
                    "state": "ACTIVE",
                }
            if getattr(agent, "last_used_fallback", False):
                return {"provider": "FALLBACK", "state": "DETERMINISTIC"}
            if getattr(agent, "last_provider_succeeded", None) is False:
                return {"provider": "PROVIDER", "state": "ERROR"}

        if self.controller.team_a_coach.is_groq_configured:
            return {"provider": "GROQ", "state": "READY"}
        if self.controller.team_a_coach.is_gemini_configured:
            return {"provider": "GEMINI", "state": "READY"}
        return {"provider": "FALLBACK", "state": "DETERMINISTIC"}


def _create_team(name: str, skill: float, stamina: float) -> Team:
    return Team(
        name=name,
        footballers=[
            Footballer(
                name=f"{name} Player {number}",
                skill=skill + ((number % 3) - 1) * 2,
                intelligence=65 + number,
                stamina=stamina + (number % 2),
            )
            for number in range(1, 12)
        ],
        tactic=TeamTactic.BALANCED,
    )


def _create_decision_makers(
    team: Team,
    *,
    api_key: str,
    model: str,
) -> tuple[
    list[ReactiveFootballer | TacticalFootballer | CognitiveFootballer],
    CognitiveFootballer,
]:
    cognitive = CognitiveFootballer(
        team.footballers[0].name,
        api_key=api_key,
        model=model,
    )
    return (
        [
            cognitive,
            *[TacticalFootballer() for _ in range(3)],
            *[ReactiveFootballer() for _ in range(7)],
        ],
        cognitive,
    )


def _team_payload(team: Team, average_energy: float) -> dict[str, Any]:
    return {
        "name": team.name,
        "tactic": team.tactic.value,
        "average_energy": round(average_energy, 1),
    }


def _cost_value(cost: Decimal | None) -> str | None:
    return format(cost, "f") if cost is not None else None


def _timeline_event_payload(event: Any) -> dict[str, Any]:
    payload = event.model_dump(mode="json")
    payload["visual"] = visual_state_for_event(
        event.type,
        event.team_side,
    ).model_dump(mode="json")
    return payload


def _playback_payload(playback: BlockPlayback) -> dict[str, Any]:
    payload = playback.model_dump(mode="json", exclude={"timeline"})
    payload["timeline"] = [
        _timeline_event_payload(event) for event in playback.timeline
    ]
    return payload
