# Idea Backlog

These are candidates, not committed roadmap items. They may be changed,
postponed, or removed.

Items in this file are not approved for implementation. An item becomes
approved only after it is explicitly moved into `CURRENT_SCOPE.md`.

## LangGraph

Reconsider when:

- the tool-based workflow becomes sufficiently complex;
- plain Python orchestration becomes difficult to maintain.

## Agent Memory

Reconsider when:

- multiple matches exist;
- agents benefit from previous match information.

## MCP + Historical Football Data

Reconsider when:

- external or real football data is introduced;
- agents need controlled access to external information.

## Reinforcement Learning Coach

Reconsider when:

- the simulation supports large-scale episodes;
- the observation, action, and reward model is stable;
- comparison with rule-based and LLM coaches adds value.

## Cognitive Player Allocation

Current implementation:

- each team has exactly one `CognitiveFootballer`;
- the other ten decision makers are deterministic `ReactiveFootballer` or
  `TacticalFootballer` implementations;
- no cognitive-player allocation choice exists;
- the single CognitiveFootballer could also be presented as captain in a
  future visual treatment, but that identity is not implemented.

Candidate direction:

- keep CognitiveFootballers limited instead of making all 11 players LLM
  agents;
- initially consider a deterministic maximum of three per team;
- let the Human Manager allocate that budget across defense, midfield, and
  attack as a real gameplay decision;
- allow distributions such as `1/1/1`, `0/1/2`, or `2/1/0` across those areas;
- allow the AI Assistant Coach to recommend an allocation without defining or
  overriding the maximum.

The limit must remain a deterministic gameplay rule. A hybrid design avoids
turning all 22 players into LLM agents without demonstrated value and preserves
reasonable latency, cost, reproducibility, explainability, and failure
handling.

Reconsider when:

- pre-match team management is approved scope;
- multiple CognitiveFootballers can meaningfully affect Match Engine inputs;
- provider-call budgets remain acceptable;
- the added orchestration complexity is justified.

## Captain / Cognitive Player Visual Identity

No captain role, armband, or cognitive marker is currently implemented.

Candidate direction:

- exactly one player is captain and may display a `C` or captain armband;
- while there is one CognitiveFootballer, that player may also be the captain;
- if multiple CognitiveFootballers are later approved, only one remains
  captain and the others use a separate, subtle cognitive indicator;
- the CognitiveFootballer may appear more active than deterministic players.

Any distinctive movement must visualize already-resolved behavior only. It
must not create possession, passes, shots, outcomes, or independent simulation.

## Rich Match Mechanics

Possible future Match Engine mechanics include:

- assists;
- yellow cards;
- red cards;
- substitutions;
- goalkeeper saves;
- injuries;
- fouls.

These may appear in the presentation only after the match model resolves them
as real events:

```text
Match Engine resolves event
        |
Match State / Event
        |
Presentation timeline
```

The presentation layer must never invent one of these mechanics as decorative
narration.

## Match Timeline Expansion

The current timeline includes presentation-derived lifecycle milestones whose
timing is deterministic from the fixed match structure: kickoff, hydration
breaks, half-time, second-half start, resumptions, and full-time. It also shows
currently supported resolved match events such as goals.

A future timeline may additionally show assists, cards, substitutions, and
saves only after those mechanics are resolved by the Match Engine and exposed
through match state or events.

## Championships / Around the League

Reconsider when:

- team selection is stable;
- multiple teams and matches are justified.

If championships and multiple matches are approved, the Human Manager's live
Match screen may include a compact "Around the League" panel. It would show
only essential information from simultaneous matches, such as team names, live
scores, goal scorers, and cards if cards have first become real mechanics. The
user's own match remains the main visual focus.

Possible future application sections are Match, Fixtures, Table, and Team.
These remain uncommitted ideas; do not create parallel matches, navigation,
placeholder pages, fixtures, or standings before they enter
`CURRENT_SCOPE.md`.
