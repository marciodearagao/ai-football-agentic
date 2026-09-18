# Test Plan

## Objective

Protect the released v0.2.0 simulation. Tests prove responsibility boundaries
and determinism; they are not intended to prove realistic football simulation.

## Current Baseline

The existing suite remains the regression baseline for:

- domain model validation;
- Reactive, Tactical, and Cognitive Footballer decisions;
- CoachAgent validation and deterministic fallback;
- Match Engine modifiers, probability bands, and seeded randomness;
- match phases, energy changes, and event ordering;
- presentation-only playback;
- provider error sanitization and usage tracking;
- FastAPI routes and browser-session serialization;
- required in-memory Team Selection and opponent assignment;
- Human Manager tactic ownership, non-mutating Assistant advice, and autonomous
  opponent coaching;
- perspective-aware, read-only coach tool calling and safe fallback;
- visualizer payload mapping and isolation from resolved match state;
- calibration aggregation.

## Permanent Engine Tests

Verify that:

- the Match Engine alone changes score and resolves outcomes;
- effective strength uses the approved energy, tactic, and behavior inputs;
- randomness remains inside its configured range;
- the same initial state and seed produce the same simulation result;
- presentation timing does not change simulation results;
- invalid agent output cannot mutate MatchState;
- unsupported domain event types are rejected.

Approved domain event types remain:

```text
GOAL
CHANCE
TACTICAL_CHANGE
ENERGY_WARNING
```

## v0.2.0 Feature Tests

These feature tests are part of the active regression suite.

### Team Selection

- only available fictional teams can be selected;
- exactly one team is controlled by the Human Manager;
- the opposing team is identified consistently;
- selection alone does not change team attributes or Match Engine rules.

### AI Assistant Coach

- can choose approved read-only context tools;
- recommends only a valid tactic;
- provides a bounded reason;
- cannot apply its recommendation directly;
- malformed or unavailable output uses deterministic fallback advice.

### Human-in-the-loop Decision

- the Human Manager may accept or override the recommendation;
- only a valid tactic can be submitted;
- no match block resolves before the required decision is complete;
- the recorded human choice, not the recommendation, reaches orchestration.

### AI Opponent Coach

- can choose approved read-only context tools;
- selects only a valid tactic;
- remains autonomous;
- malformed or unavailable output uses deterministic fallback behavior.

### Visual Presentation

- the selected human team is clearly identified;
- advice and final human choice are distinguishable;
- the visualizer maps resolved neutral, pressure, chance, and goal events to
  predefined presentation states;
- starting formations contain eleven role-labelled markers per team and keep
  both teams in their own halves;
- pre-kickoff and in-progress empty-feed messages follow presentation state;
- rendering or reading the visualizer contract does not change match results;
- events remain chronological;
- visible score changes only when the resolved goal is revealed;
- playback performs no agent or provider call;
- presentation events never mutate game state.

## Provider and Security Tests

Using mocked provider responses, verify:

- valid structured output is accepted;
- Groq tool selection omits incompatible legacy JSON mode;
- valid Groq output does not invoke Gemini;
- Groq failure invokes Gemini before deterministic fallback;
- Gemini uses the same read-only tool contract;
- local tool schemas are bounded and tool results use the correct team
  perspective;
- unknown or malformed tool calls fall back without mutating match state;
- malformed output and provider errors fall back safely;
- API keys, authorization headers, prompts, and raw payloads are not logged;
- usage counts every attempted provider call, including tool round trips;
- usage records distinguish Groq and Gemini;
- missing usage or pricing metadata remains unknown rather than fabricated;
- the application remains fully playable without provider configuration.

Normal automated tests must not require a live provider call.

## Scope Protection Review

Before completing any task:

1. read `CURRENT_SCOPE.md`;
2. confirm the task is explicitly approved;
3. verify that no `IDEA_BACKLOG.md` item entered implementation;
4. confirm that no second outcome engine or presentation-side simulation was
   introduced;
5. update affected specs and remove stale references;
6. run the complete test suite.

## Definition of Done for a Documentation-Only Task

- only documentation or comments required by the task changed;
- runtime behavior is unchanged;
- current scope and backlog remain clearly separated;
- public docs describe current behavior without promising backlog items;
- historical release notes remain intact;
- all tests pass.

## Known Dependency Warnings

The suite may report two deprecation warnings from the installed
FastAPI/Starlette test-client compatibility layer. Project code does not call
the deprecated APIs. Any dependency update requires a separate approved task.
