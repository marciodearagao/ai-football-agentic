from app.domain.enums import FootballerBehavior, TeamTactic
from app.domain.footballer import Footballer
from app.footballers.context import (
    FootballerDecisionContext,
    PreviousBlockResult,
)
from app.footballers.tactical import TacticalFootballer


def make_footballer(energy: float) -> Footballer:
    return Footballer(
        name="Tactical One",
        skill=78,
        intelligence=85,
        stamina=80,
        energy=energy,
    )


def make_context(
    score_difference: int = 0,
    team_tactic: TeamTactic = TeamTactic.BALANCED,
    previous_block_result: PreviousBlockResult | None = None,
) -> FootballerDecisionContext:
    return FootballerDecisionContext(
        score_difference=score_difference,
        team_tactic=team_tactic,
        previous_block_result=previous_block_result,
    )


def test_critical_energy_conserves_energy() -> None:
    behavior = TacticalFootballer().choose_behavior(
        make_footballer(34), make_context()
    )

    assert behavior is FootballerBehavior.CONSERVE_ENERGY


def test_losing_with_sufficient_energy_attacks() -> None:
    behavior = TacticalFootballer().choose_behavior(
        make_footballer(70), make_context(score_difference=-1)
    )

    assert behavior is FootballerBehavior.ATTACK


def test_attacking_tactic_attacks() -> None:
    behavior = TacticalFootballer().choose_behavior(
        make_footballer(70), make_context(team_tactic=TeamTactic.ATTACK)
    )

    assert behavior is FootballerBehavior.ATTACK


def test_defensive_tactic_presses() -> None:
    behavior = TacticalFootballer().choose_behavior(
        make_footballer(70), make_context(team_tactic=TeamTactic.DEFEND)
    )

    assert behavior is FootballerBehavior.PRESS


def test_stable_winning_situation_supports() -> None:
    behavior = TacticalFootballer().choose_behavior(
        make_footballer(70), make_context(score_difference=1)
    )

    assert behavior is FootballerBehavior.SUPPORT


def test_energy_rule_takes_priority_over_attacking_tactic() -> None:
    behavior = TacticalFootballer().choose_behavior(
        make_footballer(34), make_context(team_tactic=TeamTactic.ATTACK)
    )

    assert behavior is FootballerBehavior.CONSERVE_ENERGY


def test_negative_previous_block_influences_attack_when_tied() -> None:
    behavior = TacticalFootballer().choose_behavior(
        make_footballer(70),
        make_context(previous_block_result=PreviousBlockResult.NEGATIVE),
    )

    assert behavior is FootballerBehavior.ATTACK


def test_identical_input_returns_identical_behavior() -> None:
    decision_maker = TacticalFootballer()
    footballer = make_footballer(70)
    context = make_context(
        previous_block_result=PreviousBlockResult.NEGATIVE,
    )

    first_result = decision_maker.choose_behavior(footballer, context)
    second_result = decision_maker.choose_behavior(footballer, context)

    assert first_result is second_result is FootballerBehavior.ATTACK
    assert footballer.behavior is FootballerBehavior.SUPPORT
