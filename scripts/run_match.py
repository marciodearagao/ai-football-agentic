from app.domain.enums import FootballerBehavior, MatchEventType, MatchPhase, TeamTactic
from app.domain.footballer import Footballer
from app.domain.team import Team
from app.footballers.cognitive import CognitiveFootballer
from app.footballers.reactive import ReactiveFootballer
from app.footballers.tactical import TacticalFootballer
from app.match.match_controller import MatchController
from dotenv import load_dotenv


def create_team(name: str, skill: float, stamina: float) -> Team:
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


def create_decision_makers(
    team: Team,
) -> list[ReactiveFootballer | TacticalFootballer | CognitiveFootballer]:
    return [
        CognitiveFootballer(team.footballers[0].name),
        *[TacticalFootballer() for _ in range(3)],
        *[ReactiveFootballer() for _ in range(7)],
    ]


def print_block(
    controller: MatchController,
    team_a_cognitive: CognitiveFootballer,
    team_b_cognitive: CognitiveFootballer,
) -> None:
    block = controller.completed_blocks[-1]
    block_number = len(controller.completed_blocks)
    print(f"\nBlock {block_number}: {block.start_minute} to {block.end_minute}")
    for team, decision in (
        (controller.team_a, block.team_a_coach_decision),
        (controller.team_b, block.team_b_coach_decision),
    ):
        fallback = " (fallback)" if decision.reason.startswith("fallback_") else ""
        print(f"Coach {team.name}: {decision.tactic.value}{fallback}")
    for team, cognitive in (
        (controller.team_a, team_a_cognitive),
        (controller.team_b, team_b_cognitive),
    ):
        fallback = " (fallback)" if cognitive.last_used_fallback else ""
        print(
            f"{cognitive.footballer_name} behavior: "
            f"{team.footballers[0].behavior.value}{fallback}"
        )
    for event in block.events:
        if event.type in (MatchEventType.CHANCE, MatchEventType.GOAL):
            print(f"{event.type.value.title()}: {event.team_name}")
        elif event.type is MatchEventType.ENERGY_WARNING:
            print(f"Energy warning: {event.footballer_name} ({event.team_name})")
    print(f"Score: {block.state.team_a_score}-{block.state.team_b_score}")
    print(
        "Average energy: "
        f"{block.state.team_a_average_energy:.1f} / "
        f"{block.state.team_b_average_energy:.1f}"
    )
    if block.state.phase is not MatchPhase.FULL_TIME:
        print(f"--- {block.pause_label} ---")


def main() -> None:
    load_dotenv()
    team_a = create_team("AI United", skill=78, stamina=78)
    team_b = create_team("Neural FC", skill=76, stamina=80)
    team_a_decision_makers = create_decision_makers(team_a)
    team_b_decision_makers = create_decision_makers(team_b)
    team_a_cognitive = team_a_decision_makers[0]
    team_b_cognitive = team_b_decision_makers[0]
    assert isinstance(team_a_cognitive, CognitiveFootballer)
    assert isinstance(team_b_cognitive, CognitiveFootballer)
    controller = MatchController(
        team_a,
        team_b,
        team_a_decision_makers,
        team_b_decision_makers,
        seed=42,
    )

    print(f"{team_a.name} vs {team_b.name}")
    controller.start()
    print_block(controller, team_a_cognitive, team_b_cognitive)
    while controller.phase is not MatchPhase.FULL_TIME:
        controller.continue_match()
        print_block(controller, team_a_cognitive, team_b_cognitive)

    print("\nFULL TIME")
    print(
        f"{team_a.name} {controller.state.team_a_score}-"
        f"{controller.state.team_b_score} {team_b.name}"
    )
    usage = controller.usage_tracker.match_totals()
    print("\nAI USAGE")
    print(f"API calls: {usage.calls}")
    print(f"Input tokens: {usage.input_tokens:,}")
    print(f"Output tokens: {usage.output_tokens:,}")
    print(f"Total tokens: {usage.total_tokens:,}")
    print(f"Cached tokens: {usage.cached_tokens:,}")
    if usage.estimated_cost is None:
        print("Estimated cost: unavailable")
    else:
        print(f"Estimated cost: ${usage.estimated_cost:.6f}")


if __name__ == "__main__":
    main()
