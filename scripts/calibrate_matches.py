from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.coach import CoachAgent
from app.domain.enums import TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team
import app.engine.match_engine as match_engine_module
from app.engine.probability import GOAL_PROBABILITIES, ProbabilityBand
from app.footballers.cognitive import CognitiveFootballer
from app.footballers.reactive import ReactiveFootballer
from app.footballers.tactical import TacticalFootballer
from app.match.match_controller import MatchController

GoalProfile = Mapping[ProbabilityBand, float]

PROFILES: dict[str, dict[ProbabilityBand, float]] = {
    "CURRENT": {
        ProbabilityBand.LOW: 0.12,
        ProbabilityBand.MODERATE_LOW: 0.20,
        ProbabilityBand.MODERATE: 0.26,
        ProbabilityBand.HIGH: 0.36,
        ProbabilityBand.VERY_HIGH: 0.46,
    },
    "PREVIOUS_V0_1_INITIAL": {
        ProbabilityBand.LOW: 0.08,
        ProbabilityBand.MODERATE_LOW: 0.12,
        ProbabilityBand.MODERATE: 0.15,
        ProbabilityBand.HIGH: 0.25,
        ProbabilityBand.VERY_HIGH: 0.35,
    },
    "CONSERVATIVE_EXPERIMENT": {
        ProbabilityBand.LOW: 0.10,
        ProbabilityBand.MODERATE_LOW: 0.17,
        ProbabilityBand.MODERATE: 0.22,
        ProbabilityBand.HIGH: 0.32,
        ProbabilityBand.VERY_HIGH: 0.42,
    },
}


@dataclass(frozen=True)
class CalibrationResult:
    total_matches: int
    team_a_wins: int
    draws: int
    team_b_wins: int
    total_goals: int
    team_a_goals: int
    team_b_goals: int
    zero_zero: int
    one_one: int
    two_two: int
    zero_goal_matches: int
    one_goal_matches: int
    two_goal_matches: int
    three_plus_goal_matches: int
    four_plus_goal_matches: int
    maximum_total_goals: int
    scorelines: Counter[tuple[int, int]]
    provider_calls: int = 0

    @property
    def average_goals(self) -> float:
        return self.total_goals / self.total_matches

    @property
    def average_team_a_goals(self) -> float:
        return self.team_a_goals / self.total_matches

    @property
    def average_team_b_goals(self) -> float:
        return self.team_b_goals / self.total_matches

    def percentage(self, count: int) -> float:
        return (count / self.total_matches) * 100


@contextmanager
def temporary_goal_profile(profile: GoalProfile) -> Iterator[None]:
    _validate_profile(profile)
    original = match_engine_module.GOAL_PROBABILITIES
    match_engine_module.GOAL_PROBABILITIES = dict(profile)
    try:
        yield
    finally:
        match_engine_module.GOAL_PROBABILITIES = original


def run_calibration(
    match_count: int = 1000,
    goal_profile: GoalProfile | None = None,
) -> CalibrationResult:
    if match_count < 1:
        raise ValueError("Match count must be a positive integer.")
    profile = goal_profile or PROFILES["CURRENT"]
    scores: list[tuple[int, int]] = []
    provider_calls = 0
    with temporary_goal_profile(profile):
        for seed in range(1, match_count + 1):
            controller = _create_controller(seed)
            controller.run_to_full_time()
            scores.append(
                (controller.state.team_a_score, controller.state.team_b_score)
            )
            provider_calls += controller.usage_tracker.match_totals().calls
    return replace(aggregate_scores(scores), provider_calls=provider_calls)


def run_profile_experiment(
    match_count: int = 1000,
) -> dict[str, CalibrationResult]:
    return {
        name: run_calibration(match_count, profile)
        for name, profile in PROFILES.items()
    }


def aggregate_scores(scores: list[tuple[int, int]]) -> CalibrationResult:
    if not scores:
        raise ValueError("At least one score is required.")
    scorelines = Counter(scores)
    totals = [team_a + team_b for team_a, team_b in scores]
    return CalibrationResult(
        total_matches=len(scores),
        team_a_wins=sum(team_a > team_b for team_a, team_b in scores),
        draws=sum(team_a == team_b for team_a, team_b in scores),
        team_b_wins=sum(team_a < team_b for team_a, team_b in scores),
        total_goals=sum(totals),
        team_a_goals=sum(team_a for team_a, _ in scores),
        team_b_goals=sum(team_b for _, team_b in scores),
        zero_zero=scorelines[(0, 0)],
        one_one=scorelines[(1, 1)],
        two_two=scorelines[(2, 2)],
        zero_goal_matches=totals.count(0),
        one_goal_matches=totals.count(1),
        two_goal_matches=totals.count(2),
        three_plus_goal_matches=sum(total >= 3 for total in totals),
        four_plus_goal_matches=sum(total >= 4 for total in totals),
        maximum_total_goals=max(totals),
        scorelines=scorelines,
    )


def format_experiment_report(results: Mapping[str, CalibrationResult]) -> str:
    first_result = next(iter(results.values()))
    lines = [
        "AI Football Agentic - Historical Goal Probability Comparison",
        "AI provider calls disabled for calibration.",
        "Historical profiles are temporary; official CURRENT values are unchanged.",
        f"Seeds per profile: 1-{first_result.total_matches}",
        "",
    ]
    for name, result in results.items():
        lines.extend(_format_profile(name, result))
    lines.extend(_format_comparison(results))
    lines.extend(
        (
            "",
            "Approximate design targets (comparison only)",
            "Draws: 25-35%",
            "Goals per match: 2.0-2.5",
            "0-0: preferably below 15%",
            "",
            "No historical profile is applied by this comparison.",
        )
    )
    return "\n".join(lines)


def format_production_report(result: CalibrationResult) -> str:
    lines = [
        "AI Football Agentic - Production Calibration Diagnostics",
        "AI provider calls disabled for calibration.",
        "Using the official CURRENT goal-probability profile.",
        f"Seeds: 1-{result.total_matches}",
        "",
    ]
    lines.extend(_format_profile("CURRENT", result))
    return "\n".join(lines).rstrip()


def _format_profile(name: str, result: CalibrationResult) -> list[str]:
    lines = [
        f"{name} ({result.total_matches:,} matches)",
        f"  Team A wins: {result.team_a_wins:,} ({result.percentage(result.team_a_wins):.1f}%)",
        f"  Draws: {result.draws:,} ({result.percentage(result.draws):.1f}%)",
        f"  Team B wins: {result.team_b_wins:,} ({result.percentage(result.team_b_wins):.1f}%)",
        f"  Total goals: {result.total_goals:,}",
        f"  Average goals per match: {result.average_goals:.3f}",
        f"  Average Team A goals: {result.average_team_a_goals:.3f}",
        f"  Average Team B goals: {result.average_team_b_goals:.3f}",
        f"  0-0 frequency: {result.zero_zero:,}",
        f"  1-1 frequency: {result.one_one:,}",
        f"  2-2 frequency: {result.two_two:,}",
        f"  Matches with 0 goals: {result.zero_goal_matches:,}",
        f"  Matches with 1 goal: {result.one_goal_matches:,}",
        f"  Matches with 2 goals: {result.two_goal_matches:,}",
        f"  Matches with 3+ goals: {result.three_plus_goal_matches:,}",
        f"  Matches with 4+ goals: {result.four_plus_goal_matches:,}",
        f"  Maximum total goals observed: {result.maximum_total_goals}",
        f"  Provider calls: {result.provider_calls}",
        "  Most common scorelines:",
    ]
    lines.extend(
        f"    {team_a}-{team_b}: {count:,}"
        for (team_a, team_b), count in result.scorelines.most_common(10)
    )
    lines.append("")
    return lines


def _format_comparison(
    results: Mapping[str, CalibrationResult],
) -> list[str]:
    names = tuple(results)
    header = f"{'Metric':<22}" + "".join(f"{name:>15}" for name in names)
    rows = [
        ("Team A win %", lambda result: result.percentage(result.team_a_wins)),
        ("Draw %", lambda result: result.percentage(result.draws)),
        ("Team B win %", lambda result: result.percentage(result.team_b_wins)),
        ("Goals / match", lambda result: result.average_goals),
        ("0-0 %", lambda result: result.percentage(result.zero_zero)),
        ("1-1 %", lambda result: result.percentage(result.one_one)),
        ("3+ goals %", lambda result: result.percentage(result.three_plus_goal_matches)),
        ("4+ goals %", lambda result: result.percentage(result.four_plus_goal_matches)),
    ]
    lines = ["COMPARISON", header, "-" * len(header)]
    lines.extend(
        f"{label:<22}" + "".join(f"{metric(results[name]):>14.2f}%" for name in names)
        if label != "Goals / match"
        else f"{label:<22}" + "".join(f"{metric(results[name]):>15.3f}" for name in names)
        for label, metric in rows
    )
    return lines


def _validate_profile(profile: GoalProfile) -> None:
    if set(profile) != set(ProbabilityBand):
        raise ValueError("A goal profile must define every probability band.")
    if any(not 0 <= probability <= 1 for probability in profile.values()):
        raise ValueError("Goal probabilities must be between zero and one.")


def _create_controller(seed: int) -> MatchController:
    team_a = _create_team("AI United", skill=78, stamina=78)
    team_b = _create_team("Neural FC", skill=76, stamina=80)
    return MatchController(
        team_a,
        team_b,
        _create_decision_makers(team_a),
        _create_decision_makers(team_b),
        seed=seed,
        team_a_coach=CoachAgent(team_a.name, api_key="", model=""),
        team_b_coach=CoachAgent(team_b.name, api_key="", model=""),
    )


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
) -> list[ReactiveFootballer | TacticalFootballer | CognitiveFootballer]:
    return [
        CognitiveFootballer(team.footballers[0].name, api_key="", model=""),
        *[TacticalFootballer() for _ in range(3)],
        *[ReactiveFootballer() for _ in range(7)],
    ]


def main() -> None:
    try:
        match_count = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
        result = run_calibration(match_count)
    except ValueError as error:
        raise SystemExit(f"Error: {error}") from None
    print(format_production_report(result))


if __name__ == "__main__":
    main()
