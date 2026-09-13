from app.domain.enums import FootballerBehavior, TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.engine.match_engine import BlockSimulationResult, MatchEngine


def make_team(
    name: str,
    *,
    skill: float,
    energy: float = 100,
    tactic: TeamTactic = TeamTactic.BALANCED,
    behavior: FootballerBehavior = FootballerBehavior.SUPPORT,
) -> Team:
    return Team(
        name=name,
        footballers=[
            Footballer(
                name=f"{name} Footballer {number}",
                skill=skill,
                intelligence=70,
                stamina=80,
                energy=energy,
                behavior=behavior,
            )
            for number in range(1, 12)
        ],
        tactic=tactic,
    )


def test_valid_one_block_evaluation() -> None:
    result = MatchEngine(seed=10).evaluate_block(
        make_team("Team A", skill=80),
        make_team("Team B", skill=75),
    )

    assert isinstance(result, BlockSimulationResult)
    assert isinstance(result.team_a_chance, bool)
    assert isinstance(result.team_b_chance, bool)
    assert isinstance(result.team_a_goal, bool)
    assert isinstance(result.team_b_goal, bool)


def test_stronger_attacking_setup_produces_higher_attack_ratio() -> None:
    result = MatchEngine(seed=20).evaluate_block(
        make_team(
            "Strong Team",
            skill=95,
            tactic=TeamTactic.ATTACK,
            behavior=FootballerBehavior.ATTACK,
        ),
        make_team(
            "Weak Team",
            skill=45,
            energy=50,
            tactic=TeamTactic.DEFEND,
            behavior=FootballerBehavior.PRESS,
        ),
    )

    assert result.team_a_attack_ratio > result.team_b_attack_ratio


def test_strengths_and_ratios_are_never_negative() -> None:
    result = MatchEngine(seed=30).evaluate_block(
        make_team("Team A", skill=0),
        make_team("Team B", skill=0),
    )

    numeric_results = [
        result.team_a_effective_attack,
        result.team_a_effective_defense,
        result.team_b_effective_attack,
        result.team_b_effective_defense,
        result.team_a_attack_ratio,
        result.team_b_attack_ratio,
    ]
    assert all(value >= 0 for value in numeric_results)


def test_zero_strength_teams_do_not_cause_division_error() -> None:
    result = MatchEngine(seed=40).evaluate_block(
        make_team("Team A", skill=0),
        make_team("Team B", skill=0),
    )

    assert result.team_a_attack_ratio == 0
    assert result.team_b_attack_ratio == 0


def test_result_contains_only_approved_event_concepts() -> None:
    result = MatchEngine(seed=50).evaluate_block(
        make_team("Team A", skill=80),
        make_team("Team B", skill=75),
    )
    event_fields = {
        field_name
        for field_name in type(result).model_fields
        if field_name.endswith(("_chance", "_goal"))
    }

    assert event_fields == {
        "team_a_chance",
        "team_b_chance",
        "team_a_goal",
        "team_b_goal",
    }


def test_same_inputs_and_seed_produce_same_block_result() -> None:
    team_a = make_team("Team A", skill=80)
    team_b = make_team("Team B", skill=75)

    first_result = MatchEngine(seed=60).evaluate_block(team_a, team_b)
    second_result = MatchEngine(seed=60).evaluate_block(team_a, team_b)

    assert first_result == second_result


def test_different_seeds_produce_different_block_results() -> None:
    team_a = make_team("Team A", skill=80)
    team_b = make_team("Team B", skill=75)

    first_result = MatchEngine(seed=1).evaluate_block(team_a, team_b)
    second_result = MatchEngine(seed=2).evaluate_block(team_a, team_b)

    assert first_result != second_result


def test_stronger_team_scores_more_often_in_seeded_smoke_test() -> None:
    strong_team = make_team(
        "Strong Team",
        skill=95,
        tactic=TeamTactic.ATTACK,
        behavior=FootballerBehavior.ATTACK,
    )
    weak_team = make_team(
        "Weak Team",
        skill=45,
        energy=50,
        tactic=TeamTactic.DEFEND,
        behavior=FootballerBehavior.PRESS,
    )

    results = [
        MatchEngine(seed=seed).evaluate_block(strong_team, weak_team)
        for seed in range(200)
    ]
    strong_goals = sum(result.team_a_goal for result in results)
    weak_goals = sum(result.team_b_goal for result in results)

    assert strong_goals > weak_goals
