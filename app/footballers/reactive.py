from app.domain.enums import FootballerBehavior, TeamTactic
from app.domain.footballer import Footballer
from app.footballers.context import FootballerDecisionContext

LOW_ENERGY_THRESHOLD = 40


class ReactiveFootballer:
    def choose_behavior(
        self,
        footballer: Footballer,
        context: FootballerDecisionContext,
    ) -> FootballerBehavior:
        if footballer.energy < LOW_ENERGY_THRESHOLD:
            return FootballerBehavior.CONSERVE_ENERGY

        if context.score_difference < 0:
            return FootballerBehavior.ATTACK

        if context.team_tactic is TeamTactic.DEFEND:
            return FootballerBehavior.PRESS

        return FootballerBehavior.SUPPORT
