from app.domain.enums import FootballerBehavior, TeamTactic
from app.domain.footballer import Footballer
from app.footballers.context import FootballerDecisionContext
from app.footballers.reactive import ReactiveFootballer


def make_footballer(energy: float) -> Footballer:
    return Footballer(
        name="Reactive One",
        skill=70,
        intelligence=45,
        stamina=75,
        energy=energy,
    )


def make_context(
    score_difference: int = 0,
    team_tactic: TeamTactic = TeamTactic.BALANCED,
) -> FootballerDecisionContext:
    return FootballerDecisionContext(
        score_difference=score_difference,
        team_tactic=team_tactic,
    )


def test_low_energy_conserves_energy() -> None:
    behavior = ReactiveFootballer().choose_behavior(
        make_footballer(39), make_context()
    )

    assert behavior is FootballerBehavior.CONSERVE_ENERGY


def test_losing_with_sufficient_energy_attacks() -> None:
    behavior = ReactiveFootballer().choose_behavior(
        make_footballer(80), make_context(score_difference=-1)
    )

    assert behavior is FootballerBehavior.ATTACK


def test_defensive_tactic_presses() -> None:
    behavior = ReactiveFootballer().choose_behavior(
        make_footballer(80), make_context(team_tactic=TeamTactic.DEFEND)
    )

    assert behavior is FootballerBehavior.PRESS


def test_neutral_state_supports() -> None:
    behavior = ReactiveFootballer().choose_behavior(
        make_footballer(80), make_context()
    )

    assert behavior is FootballerBehavior.SUPPORT


def test_low_energy_takes_priority_over_losing() -> None:
    behavior = ReactiveFootballer().choose_behavior(
        make_footballer(39), make_context(score_difference=-2)
    )

    assert behavior is FootballerBehavior.CONSERVE_ENERGY


def test_identical_input_returns_identical_behavior() -> None:
    decision_maker = ReactiveFootballer()
    footballer = make_footballer(75)
    context = make_context(score_difference=-1)

    first_result = decision_maker.choose_behavior(footballer, context)
    second_result = decision_maker.choose_behavior(footballer, context)

    assert first_result is second_result is FootballerBehavior.ATTACK
    assert footballer.behavior is FootballerBehavior.SUPPORT
