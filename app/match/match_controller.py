from collections.abc import Sequence

from pydantic import BaseModel

from app.agents.coach import CoachAgent, CoachDecision
from app.agents.coach_context import CoachContext
from app.domain.enums import FootballerBehavior, MatchPhase, TeamTactic
from app.domain.footballer import Footballer
from app.domain.match_state import MatchState
from app.domain.team import Team
from app.engine.match_engine import BlockSimulationResult, MatchEngine
from app.footballers.context import (
    FootballerDecisionContext,
    PreviousBlockResult,
    previous_block_result_for_team,
)
from app.footballers.cognitive import CognitiveFootballer
from app.footballers.cognitive_context import CognitiveFootballerContext
from app.footballers.reactive import ReactiveFootballer
from app.footballers.tactical import TacticalFootballer
from app.match.energy import consume_team_energy
from app.match.events import (
    MatchEvent,
    create_block_events,
    create_tactical_change_event,
    determine_block_advantage,
    score_after_block,
)
from app.match.phases import CONTINUATION_PHASES, MATCH_BLOCKS
from app.usage.models import AgentType, make_agent_id
from app.usage.tracker import UsageTracker

FootballerDecisionMaker = (
    ReactiveFootballer | TacticalFootballer | CognitiveFootballer
)


class InvalidMatchTransition(RuntimeError):
    pass


class CompletedMatchBlock(BaseModel):
    phase: MatchPhase
    start_minute: str
    end_minute: str
    pause_label: str
    team_a_coach_decision: CoachDecision
    team_b_coach_decision: CoachDecision
    simulation: BlockSimulationResult
    events: list[MatchEvent]
    state: MatchState


class MatchController:
    def __init__(
        self,
        team_a: Team,
        team_b: Team,
        team_a_decision_makers: Sequence[FootballerDecisionMaker],
        team_b_decision_makers: Sequence[FootballerDecisionMaker],
        seed: int | None = None,
        team_a_coach: CoachAgent | None = None,
        team_b_coach: CoachAgent | None = None,
    ) -> None:
        self._validate_decision_makers(team_a, team_a_decision_makers)
        self._validate_decision_makers(team_b, team_b_decision_makers)
        self.team_a = team_a
        self.team_b = team_b
        self._team_a_decision_makers = tuple(team_a_decision_makers)
        self._team_b_decision_makers = tuple(team_b_decision_makers)
        self.team_a_coach = team_a_coach or CoachAgent(team_a.name)
        self.team_b_coach = team_b_coach or CoachAgent(team_b.name)
        self._engine = MatchEngine(seed=seed)
        self.usage_tracker = UsageTracker()
        self.completed_blocks: list[CompletedMatchBlock] = []
        self.state = MatchState(
            minute=0,
            team_a_score=0,
            team_b_score=0,
            team_a_tactic=team_a.tactic,
            team_b_tactic=team_b.tactic,
            team_a_strength=team_a.base_strength,
            team_b_strength=team_b.base_strength,
            team_a_average_energy=self._average_energy(team_a),
            team_b_average_energy=self._average_energy(team_b),
        )

    @property
    def phase(self) -> MatchPhase:
        return self.state.phase

    def start(self) -> CompletedMatchBlock:
        if self.phase is not MatchPhase.NOT_STARTED:
            raise InvalidMatchTransition("A match can only start once.")
        return self._simulate_block(0)

    def continue_match(self) -> CompletedMatchBlock:
        block_index = CONTINUATION_PHASES.get(self.phase)
        if block_index is None:
            raise InvalidMatchTransition(
                f"The match cannot continue from phase {self.phase.value}."
            )
        return self._simulate_block(block_index)

    def run_to_full_time(self) -> tuple[CompletedMatchBlock, ...]:
        if self.phase is not MatchPhase.NOT_STARTED:
            raise InvalidMatchTransition("A complete run requires a new match.")

        self.start()
        while self.phase is not MatchPhase.FULL_TIME:
            self.continue_match()
        return tuple(self.completed_blocks)

    def _simulate_block(self, block_index: int) -> CompletedMatchBlock:
        block = MATCH_BLOCKS[block_index]
        team_a_coach_context = CoachContext.from_match_state(
            self.state,
            is_team_a=True,
            phase=block.phase,
        )
        team_b_coach_context = CoachContext.from_match_state(
            self.state,
            is_team_a=False,
            phase=block.phase,
        )
        team_a_calls_before = self.team_a_coach.provider_call_count
        team_a_metadata_before = len(self.team_a_coach.response_metadata)
        team_a_coach_decision = self.team_a_coach.choose_tactic(team_a_coach_context)
        self._record_usage(
            agent_id=make_agent_id(AgentType.COACH, self.team_a.name),
            agent_type=AgentType.COACH,
            model=self.team_a_coach.model,
            provider_calls_before=team_a_calls_before,
            provider_calls_after=self.team_a_coach.provider_call_count,
            metadata_before=team_a_metadata_before,
            response_metadata=self.team_a_coach.response_metadata,
            used_fallback=self.team_a_coach.last_used_fallback,
        )
        team_b_calls_before = self.team_b_coach.provider_call_count
        team_b_metadata_before = len(self.team_b_coach.response_metadata)
        team_b_coach_decision = self.team_b_coach.choose_tactic(team_b_coach_context)
        self._record_usage(
            agent_id=make_agent_id(AgentType.COACH, self.team_b.name),
            agent_type=AgentType.COACH,
            model=self.team_b_coach.model,
            provider_calls_before=team_b_calls_before,
            provider_calls_after=self.team_b_coach.provider_call_count,
            metadata_before=team_b_metadata_before,
            response_metadata=self.team_b_coach.response_metadata,
            used_fallback=self.team_b_coach.last_used_fallback,
        )
        team_a_previous_tactic = self.team_a.tactic
        team_b_previous_tactic = self.team_b.tactic
        self.team_a.tactic = TeamTactic(team_a_coach_decision.tactic)
        self.team_b.tactic = TeamTactic(team_b_coach_decision.tactic)
        tactical_events = [
            event
            for event in (
                create_tactical_change_event(
                    self.team_a.name,
                    team_a_previous_tactic,
                    self.team_a.tactic,
                    block.phase,
                    block.start_minute,
                ),
                create_tactical_change_event(
                    self.team_b.name,
                    team_b_previous_tactic,
                    self.team_b.tactic,
                    block.phase,
                    block.start_minute,
                ),
            )
            if event is not None
        ]
        self._select_team_behaviors(
            self.team_a,
            self.team_b,
            self._team_a_decision_makers,
            self.state.team_a_score - self.state.team_b_score,
            previous_block_result_for_team(
                self.state.previous_block_result,
                is_team_a=True,
            ),
            block.phase,
        )
        self._select_team_behaviors(
            self.team_b,
            self.team_a,
            self._team_b_decision_makers,
            self.state.team_b_score - self.state.team_a_score,
            previous_block_result_for_team(
                self.state.previous_block_result,
                is_team_a=False,
            ),
            block.phase,
        )

        simulation = self._engine.evaluate_block(self.team_a, self.team_b)
        team_a_score, team_b_score = score_after_block(
            self.state.team_a_score,
            self.state.team_b_score,
            simulation,
        )
        team_a_warnings = consume_team_energy(self.team_a)
        team_b_warnings = consume_team_energy(self.team_b)
        events = tactical_events + create_block_events(
            simulation,
            self.team_a,
            self.team_b,
            block.phase,
            block.end_minute,
            team_a_warnings,
            team_b_warnings,
        )
        advantage = determine_block_advantage(simulation)

        self.state = MatchState(
            phase=block.next_phase,
            minute=block.state_minute,
            team_a_score=team_a_score,
            team_b_score=team_b_score,
            team_a_tactic=self.team_a.tactic,
            team_b_tactic=self.team_b.tactic,
            team_a_strength=self.team_a.base_strength,
            team_b_strength=self.team_b.base_strength,
            team_a_average_energy=self._average_energy(self.team_a),
            team_b_average_energy=self._average_energy(self.team_b),
            previous_block_result=advantage.value,
        )
        completed_block = CompletedMatchBlock(
            phase=block.phase,
            start_minute=block.start_minute,
            end_minute=block.end_minute,
            pause_label=block.pause_label,
            team_a_coach_decision=team_a_coach_decision,
            team_b_coach_decision=team_b_coach_decision,
            simulation=simulation,
            events=events,
            state=self.state.model_copy(deep=True),
        )
        self.completed_blocks.append(completed_block)
        return completed_block

    def _select_team_behaviors(
        self,
        team: Team,
        opponent: Team,
        decision_makers: tuple[FootballerDecisionMaker, ...],
        score_difference: int,
        previous_block_result: PreviousBlockResult | None,
        phase: MatchPhase,
    ) -> None:
        context = FootballerDecisionContext(
            score_difference=score_difference,
            team_tactic=team.tactic,
            previous_block_result=previous_block_result,
        )
        for footballer, decision_maker in zip(
            team.footballers, decision_makers, strict=True
        ):
            if isinstance(decision_maker, CognitiveFootballer):
                cognitive_context = CognitiveFootballerContext.for_footballer(
                    footballer,
                    phase=phase,
                    score_difference=score_difference,
                    team_tactic=team.tactic,
                    team_average_energy=self._average_energy(team),
                    opponent_average_energy=self._average_energy(opponent),
                    previous_block_result=previous_block_result,
                )
                calls_before = decision_maker.provider_call_count
                metadata_before = len(decision_maker.response_metadata)
                decision = decision_maker.choose_behavior(
                    footballer,
                    cognitive_context,
                )
                self._record_usage(
                    agent_id=make_agent_id(
                        AgentType.COGNITIVE_FOOTBALLER,
                        footballer.name,
                    ),
                    agent_type=AgentType.COGNITIVE_FOOTBALLER,
                    model=decision_maker.model,
                    provider_calls_before=calls_before,
                    provider_calls_after=decision_maker.provider_call_count,
                    metadata_before=metadata_before,
                    response_metadata=decision_maker.response_metadata,
                    used_fallback=decision_maker.last_used_fallback,
                )
            else:
                decision = decision_maker.choose_behavior(footballer, context)
            footballer.behavior = FootballerBehavior(decision)

    def _record_usage(
        self,
        *,
        agent_id: str,
        agent_type: AgentType,
        model: str | None,
        provider_calls_before: int,
        provider_calls_after: int,
        metadata_before: int,
        response_metadata: Sequence[object],
        used_fallback: bool,
    ) -> None:
        if provider_calls_after <= provider_calls_before:
            return
        metadata = (
            response_metadata[-1]
            if len(response_metadata) > metadata_before
            else None
        )
        self.usage_tracker.record_provider_attempt(
            agent_id=agent_id,
            agent_type=agent_type,
            model=model,
            used_fallback=used_fallback,
            response_metadata=metadata,
        )

    @staticmethod
    def _average_energy(team: Team) -> float:
        return sum(footballer.energy for footballer in team.footballers) / len(
            team.footballers
        )

    @staticmethod
    def _validate_decision_makers(
        team: Team,
        decision_makers: Sequence[FootballerDecisionMaker],
    ) -> None:
        if len(decision_makers) != len(team.footballers):
            raise ValueError("Each Footballer requires exactly one decision maker.")
        if any(
            not isinstance(
                decision_maker,
                (ReactiveFootballer, TacticalFootballer, CognitiveFootballer),
            )
            for decision_maker in decision_makers
        ):
            raise ValueError("Unsupported Footballer decision type.")
        if sum(
            isinstance(decision_maker, CognitiveFootballer)
            for decision_maker in decision_makers
        ) > 1:
            raise ValueError("At most one CognitiveFootballer is allowed per team.")
