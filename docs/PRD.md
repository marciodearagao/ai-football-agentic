# Product Requirements Document

## Product

AI Football Agentic - v0.2.0

## Status

This document defines the released product requirements for v0.2.0.
`CURRENT_SCOPE.md` remains authoritative for scope and release status.

## Goal

Extend the existing small browser-based football simulation so a Human Manager
can select and control one fictional team, receive bounded tactical advice from
an AI Assistant Coach, and decide the human team's tactic while an AI Opponent
Coach controls the other team.

The project remains an abstract management simulation, not a detailed football
or physics simulator.

## User

The user is the Human Manager. Within the approved v0.2.0 scope, the Human
Manager must be able to:

1. select one of the available fictional teams;
2. identify the selected team and opponent clearly;
3. receive a tactical recommendation from the AI Assistant Coach;
4. accept or override the recommendation with a valid tactic;
5. advance the match after making the required decision;
6. observe already resolved match state and events;
7. complete the match and inspect the final result.

The AI Assistant Coach recommends but never makes the final human-team tactic
decision. The AI Opponent Coach remains autonomous.

## Core Product Rules

- One Human Manager controls one team.
- Team selection uses fictional teams only.
- Tactical choices remain `ATTACK`, `BALANCED`, or `DEFEND`.
- Provider output is untrusted until validated.
- Invalid or unavailable AI output uses deterministic fallback behavior.
- The Match Engine alone resolves chances, goals, energy, and outcomes.
- The visual layer presents resolved state and events without simulating them.

## Match Structure

The existing four-block match remains the baseline:

1. minutes 1-25;
2. minutes 26-45+5;
3. minutes 46-70;
4. minutes 71-90+5.

Breaks remain presentation and interaction boundaries. Any tactical interaction
must complete before the next block is resolved.

## AI Responsibilities

### AI Assistant Coach

- chooses approved read-only tools when it needs match context;
- recommends one valid tactic and a short reason;
- cannot apply its recommendation directly;
- cannot request or determine a goal or result.

### AI Opponent Coach

- chooses approved read-only tools when it needs match context;
- chooses one valid opponent tactic autonomously;
- cannot request or determine a goal or result.

## Presentation

The browser should clearly present:

- selected human team and opponent;
- current score, match time, tactics, and energy;
- AI Assistant recommendation and Human Manager choice;
- opponent tactical decisions at the appropriate level of visibility;
- chronological match events and final result;
- current provider status and usage already supported by the application.

Presentation remains simple and does not add autonomous visual players or
unimplemented football mechanics.

The current visualizer uses a horizontal SVG field and predefined movements for
already resolved neutral, pressure, chance, and goal states. It is a replaceable
presentation component and does not infer possession or match outcomes.

## Acceptance Criteria

v0.2.0 delivers and tests the in-scope items while preserving these properties:

- Human Manager selects and controls one team;
- AI Assistant advice is optional and cannot override the human decision;
- AI Opponent Coach remains autonomous;
- deterministic fallback keeps the match playable;
- Match Engine outcomes remain authoritative and reproducible by seed;
- visual playback does not alter resolved state;
- automated tests pass.

## Exclusions

The exclusions in `CURRENT_SCOPE.md` apply. Backlog candidates in
`IDEA_BACKLOG.md` are not requirements and must not be implemented unless moved
into the current scope through an explicit approval.
