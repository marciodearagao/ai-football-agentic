from app.domain.enums import FootballerBehavior, TeamTactic
from app.domain.footballer import Footballer
from app.footballers.context import FootballerDecisionContext, PreviousBlockResult

CRITICAL_ENERGY_THRESHOLD = 35


class TacticalFootballer:
    def choose_behavior(
        self,
        footballer: Footballer,
        context: FootballerDecisionContext,
    ) -> FootballerBehavior:
        if footballer.energy < CRITICAL_ENERGY_THRESHOLD:
            return FootballerBehavior.CONSERVE_ENERGY

        if context.score_difference < 0:
            return FootballerBehavior.ATTACK

        if (
            context.score_difference == 0
            and context.previous_block_result is PreviousBlockResult.NEGATIVE
        ):
            return FootballerBehavior.ATTACK

        if context.team_tactic is TeamTactic.ATTACK:
            return FootballerBehavior.ATTACK

        if context.team_tactic is TeamTactic.DEFEND:
            return FootballerBehavior.PRESS

        return FootballerBehavior.SUPPORT
