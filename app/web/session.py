import secrets
from decimal import Decimal
from threading import Lock
from typing import Any

from app.domain.enums import MatchPhase, TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.footballers.cognitive import CognitiveFootballer
from app.footballers.reactive import ReactiveFootballer
from app.footballers.tactical import TacticalFootballer
from app.match.match_controller import InvalidMatchTransition, MatchController
from app.web.presentation import BlockPlayback, build_block_playback


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


class WebMatchSession:
    """Own the single local match exposed by the browser application."""

    def __init__(self, *, seed: int | None = None) -> None:
        self._fixed_seed = seed
        self._lock = Lock()
        self._create_match()

    def start(self) -> dict[str, Any]:
        with self._lock:
            playback = self._simulate_for_playback(start=True)
            return self._state_payload(playback)

    def continue_match(self) -> dict[str, Any]:
        with self._lock:
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
        team_a = _create_team("AI United", skill=78, stamina=78)
        team_b = _create_team("Neural FC", skill=76, stamina=80)
        team_a_makers, self._team_a_cognitive = _create_decision_makers(team_a)
        team_b_makers, self._team_b_cognitive = _create_decision_makers(team_b)
        self.controller = MatchController(
            team_a,
            team_b,
            team_a_makers,
            team_b_makers,
            seed=self.match_seed,
        )

    def _simulate_for_playback(self, *, start: bool) -> BlockPlayback:
        state = self.controller.state
        start_score = (state.team_a_score, state.team_b_score)
        start_energy = (
            state.team_a_average_energy,
            state.team_b_average_energy,
        )
        block = self.controller.start() if start else self.controller.continue_match()
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
        return playback

    def _last_narrative_text(self) -> str | None:
        for playback in reversed(self._presentation_blocks):
            for event in reversed(playback.timeline):
                if event.kind == "PRESENTATION" and event.type != "QUIET_MATCH":
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
        can_continue = state.phase in {
            MatchPhase.FIRST_HYDRATION,
            MatchPhase.HALF_TIME,
            MatchPhase.SECOND_HYDRATION,
        }

        return {
            "phase": state.phase.value,
            "display_period": PHASE_LABELS[state.phase],
            "display_clock": (
                self._presentation_blocks[-1].clocks[-1]
                if self._presentation_blocks
                else "0'"
            ),
            "completed_blocks": len(blocks),
            "progress_percent": PROGRESS_BY_PHASE[state.phase],
            "team_a": _team_payload(controller.team_a, state.team_a_average_energy),
            "team_b": _team_payload(controller.team_b, state.team_b_average_energy),
            "score": {
                "team_a": state.team_a_score,
                "team_b": state.team_b_score,
            },
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
                event.model_dump(mode="json")
                for block_playback in self._presentation_blocks
                for event in block_playback.timeline
            ],
            "playback": playback.model_dump(mode="json") if playback else None,
            "coach_decisions": (
                {
                    "team_a": {
                        "team_name": controller.team_a.name,
                        "tactic": latest_block.team_a_coach_decision.tactic.value,
                    },
                    "team_b": {
                        "team_name": controller.team_b.name,
                        "tactic": latest_block.team_b_coach_decision.tactic.value,
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
            "groq_status": self._groq_status(),
            "can_start": state.phase is MatchPhase.NOT_STARTED,
            "can_continue": can_continue,
            "is_full_time": state.phase is MatchPhase.FULL_TIME,
        }

    def _groq_status(self) -> str:
        agents = (
            self.controller.team_a_coach,
            self.controller.team_b_coach,
            self._team_a_cognitive,
            self._team_b_cognitive,
        )
        if not all(agent.is_configured for agent in agents):
            return "NOT_CONFIGURED"
        if any(agent.last_error is not None for agent in agents):
            return "ERROR"
        return "CONNECTED"


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
) -> tuple[
    list[ReactiveFootballer | TacticalFootballer | CognitiveFootballer],
    CognitiveFootballer,
]:
    cognitive = CognitiveFootballer(team.footballers[0].name)
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
