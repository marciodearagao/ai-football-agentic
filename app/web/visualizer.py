from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


VisualMode = Literal["NEUTRAL", "PRESSURE", "CHANCE", "GOAL"]
TeamSideValue = Literal["team_a", "team_b"]
PlayerRole = Literal["GOALKEEPER", "DEFENDER", "MIDFIELDER", "ATTACKER"]


class VisualizerFrame(BaseModel):
    """Presentation-only instruction derived from an already resolved event."""

    model_config = ConfigDict(extra="forbid")

    mode: VisualMode
    attacking_side: TeamSideValue | None = None


class FormationMarker(BaseModel):
    """One presentation marker in a predefined starting formation."""

    model_config = ConfigDict(extra="forbid")

    role: PlayerRole
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=60)


PRESSURE_EVENT_TYPES = {
    "PRESSURE",
    "MOMENTUM",
    "DOMINANCE",
    "LATE_PUSH",
    "REACTION",
}


def visual_state_for_event(
    event_type: str,
    team_side: TeamSideValue | None,
) -> VisualizerFrame:
    """Map resolved presentation data to a predefined visual pattern."""
    if event_type == "GOAL":
        return VisualizerFrame(mode="GOAL", attacking_side=team_side)
    if event_type == "CHANCE":
        return VisualizerFrame(mode="CHANCE", attacking_side=team_side)
    if event_type in PRESSURE_EVENT_TYPES:
        return VisualizerFrame(mode="PRESSURE", attacking_side=team_side)
    return VisualizerFrame(mode="NEUTRAL")


def visualizer_payload(team_a_name: str, team_b_name: str) -> dict[str, object]:
    team_a_formation = _team_a_formation()
    team_b_formation = _mirror_formation(team_a_formation)
    return {
        "schema_version": 1,
        "teams": {
            "team_a": {"name": team_a_name},
            "team_b": {"name": team_b_name},
        },
        "formations": {
            "team_a": [
                marker.model_dump(mode="json") for marker in team_a_formation
            ],
            "team_b": [
                marker.model_dump(mode="json")
                for marker in team_b_formation
            ],
        },
        "animation_targets": _animation_targets(
            team_a_formation,
            team_b_formation,
        ),
        "frame": VisualizerFrame(mode="NEUTRAL").model_dump(mode="json"),
    }


def _team_a_formation() -> tuple[FormationMarker, ...]:
    """Return a visual-only 4-3-3 entirely inside team A's own half."""
    return (
        FormationMarker(role="GOALKEEPER", x=7, y=30),
        FormationMarker(role="DEFENDER", x=18, y=9),
        FormationMarker(role="DEFENDER", x=18, y=23),
        FormationMarker(role="DEFENDER", x=18, y=37),
        FormationMarker(role="DEFENDER", x=18, y=51),
        FormationMarker(role="MIDFIELDER", x=31, y=14),
        FormationMarker(role="MIDFIELDER", x=33, y=30),
        FormationMarker(role="MIDFIELDER", x=31, y=46),
        FormationMarker(role="ATTACKER", x=44, y=18),
        FormationMarker(role="ATTACKER", x=46, y=30),
        FormationMarker(role="ATTACKER", x=44, y=42),
    )


def _mirror_formation(
    formation: tuple[FormationMarker, ...],
) -> tuple[FormationMarker, ...]:
    return tuple(
        FormationMarker(role=marker.role, x=100 - marker.x, y=marker.y)
        for marker in formation
    )


def _animation_targets(
    team_a_formation: tuple[FormationMarker, ...],
    team_b_formation: tuple[FormationMarker, ...],
) -> dict[str, dict[str, dict[str, list[dict[str, object]]]]]:
    """Return presentation-only targets for either team's attacking direction."""
    team_a_attack = {
        mode: {
            "team_a": _position_markers(team_a_formation, attacking),
            "team_b": _position_markers(team_b_formation, defending),
        }
        for mode, (attacking, defending) in _TEAM_A_TARGET_COORDINATES.items()
    }
    team_b_attack = {
        mode: {
            "team_a": _dump_markers(_mirror_formation(frame["team_b"])),
            "team_b": _dump_markers(_mirror_formation(frame["team_a"])),
        }
        for mode, frame in {
            mode: {
                side: tuple(FormationMarker.model_validate(marker) for marker in markers)
                for side, markers in targets.items()
            }
            for mode, targets in team_a_attack.items()
        }.items()
    }
    return {"team_a": team_a_attack, "team_b": team_b_attack}


def _position_markers(
    formation: tuple[FormationMarker, ...],
    coordinates: tuple[tuple[float, float], ...],
) -> list[dict[str, object]]:
    return _dump_markers(
        tuple(
            FormationMarker(role=marker.role, x=x, y=y)
            for marker, (x, y) in zip(formation, coordinates, strict=True)
        )
    )


def _dump_markers(
    markers: tuple[FormationMarker, ...],
) -> list[dict[str, object]]:
    return [marker.model_dump(mode="json") for marker in markers]


# Coordinates are visual choreography, not player positions used by gameplay.
_TEAM_A_TARGET_COORDINATES = {
    "PRESSURE": (
        (
            (8, 30),
            (28, 9), (30, 23), (30, 37), (28, 51),
            (52, 14), (55, 30), (52, 46),
            (61, 18), (66, 30), (61, 42),
        ),
        (
            (94, 30),
            (82, 13), (80, 24), (80, 36), (82, 47),
            (70, 17), (68, 30), (70, 43),
            (62, 21), (60, 30), (62, 39),
        ),
    ),
    "CHANCE": (
        (
            (9, 30),
            (35, 10), (38, 23), (38, 37), (35, 50),
            (67, 15), (72, 30), (67, 45),
            (83, 18), (89, 30), (83, 42),
        ),
        (
            (95, 30),
            (88, 16), (86, 25), (86, 35), (88, 44),
            (78, 19), (76, 30), (78, 41),
            (70, 23), (68, 30), (70, 37),
        ),
    ),
    "GOAL": (
        (
            (10, 30),
            (48, 11), (51, 24), (51, 36), (48, 49),
            (76, 16), (80, 30), (76, 44),
            (91, 21), (97, 30), (91, 39),
        ),
        (
            (96, 30),
            (91, 18), (89, 26), (89, 34), (91, 42),
            (84, 21), (82, 30), (84, 39),
            (76, 24), (74, 30), (76, 36),
        ),
    ),
}
