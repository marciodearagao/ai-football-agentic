# Game Specification

## Status

This specification records the released v0.2.0 simulation rules and interaction
constraints.

## Core Principle

The game is a probabilistic football simulation. Agents and the Human Manager
choose bounded inputs. The Match Engine determines consequences.

No agent, tool, visual component, or human action directly decides:

- goals;
- final scores;
- match outcomes.

## Match Structure

One match has four blocks:

1. minutes 1-25;
2. minutes 26-45+5;
3. minutes 46-70;
4. minutes 71-90+5.

There are hydration breaks after minutes 25 and 70, half-time after the second
block, and full-time after the fourth block.

## Teams and Control

The application contains two fictional teams and requires the Human Manager to
select one before kickoff. The selected side is stored only in the current
in-memory web session, and the other existing team is identified as the
opponent. Starting a match without a selection is invalid. Starting a new match
after full time clears the selection.

Team selection must not silently alter attributes, probabilities, calibrated
engine values, match structure, internal team ordering, or seeded outcomes.

## Tactic Decision Contract

Allowed team tactics remain:

```text
ATTACK
BALANCED
DEFEND
```

For the human-controlled team:

1. the AI Assistant Coach recommends one valid tactic and a short reason;
2. the Human Manager may accept or override the recommendation;
3. the validated Human Manager choice is stored in the in-memory session;
4. that stored choice is supplied to the next Match Engine block.

For the opposing team, the AI Opponent Coach autonomously selects one valid
tactic. Invalid or unavailable AI output must use a deterministic fallback.

The selected team's autonomous CoachAgent is not consulted. An Assistant Coach
recommendation never updates the team tactic. Only the Human Manager choice is
applied when the block begins.

Before returning a recommendation or autonomous opponent tactic, the relevant
coach may choose to call any of these application-executed read-only tools:

```text
get_score()
get_match_phase()
get_team_energy()
get_opponent_energy()
get_current_tactic()
```

Values are returned from that coach's team perspective. Tool calls cannot
change tactics, score, energy, events, MatchState, or Match Engine state. The
final output still uses the same validated tactic-and-reason contract, with the
same deterministic fallback on any provider, tool, or validation failure.

Assistant and opponent coaching attempt Groq first. A Groq request, tool, or
validation failure may invoke Gemini with the same read-only tools. Only if
Gemini also fails is the deterministic tactic returned. A valid Groq decision
never invokes Gemini, and neither provider can apply an Assistant recommendation.

## Footballer Attributes

Each Footballer has:

```text
skill
intelligence
stamina
energy
```

- `skill` contributes to team strength.
- `intelligence` selects the internal decision implementation.
- `stamina` influences energy loss.
- `energy` is dynamic match state clamped to `0-100`.

After each simulation block:

```text
stamina_factor = 1.20 - (stamina / 250)
energy_loss = 12 * stamina_factor * behavior_factor
```

Behavior factors are:

```text
ATTACK           1.15
SUPPORT          1.00
PRESS            1.20
CONSERVE_ENERGY  0.65
```

There is no recovery during pauses. An `ENERGY_WARNING` is generated only when
a Footballer crosses from energy `>= 40` to energy `< 40`.

## Internal Footballer Decision Types

These implementation names are not user-facing:

- `ReactiveFootballer`: current-state Python rules;
- `TacticalFootballer`: context-aware Python rules;
- `CognitiveFootballer`: structured Groq decision with TacticalFootballer
  fallback.

The current implementation has exactly one CognitiveFootballer, three
TacticalFootballers, and seven ReactiveFootballers per team. Each type selects
only an existing Footballer behavior. The resulting behaviors contribute to
the existing team-level attack and defense modifiers used by the Match Engine;
they do not simulate individual football actions.

There is no 11-player LLM-agent simulation, captain role, or cognitive-player
allocation feature. The number and placement of CognitiveFootballers cannot be
configured by the Human Manager in the current version.

## Footballer Behaviors

```text
ATTACK
SUPPORT
PRESS
CONSERVE_ENERGY
```

Behaviors are abstract and do not represent individual passes, shots, tackles,
positions, or physical actions.

The team-level adjustments contributed by each Footballer are:

```text
ATTACK
attack: +3%
defense: unchanged

SUPPORT
attack: +2%
defense: +2%

PRESS
attack: unchanged
defense: +3%

CONSERVE_ENERGY
attack: -3%
defense: -3%
```

Adjustments for all 11 Footballers are summed independently for attack and
defense, then capped to `-10%` through `+10%`.

## Base and Effective Strength

Base team strength is:

```text
average(skill of starting Footballers)
```

There is no positional weighting in the current Match Engine.

Effective attack and defense conceptually combine:

```text
base strength
* energy modifier
* tactic modifier
* Footballer behavior modifier
* controlled randomness
```

## Energy Modifiers

```text
90-100  -> 1.00
75-89   -> 0.97
60-74   -> 0.92
40-59   -> 0.85
<40     -> 0.75
```

## Tactical Modifiers

```text
ATTACK
attack: +8%
defense: -6%

BALANCED
neutral

DEFEND
attack: -8%
defense: +8%
```

## Randomness

The engine applies controlled randomness in the range:

```text
0.90-1.10
```

An optional seed makes the complete four-block match reproducible from
identical initial state.

## Goal and Chance Probability

Probability depends primarily on attacking effective strength divided by
defending effective strength:

```text
ratio < 0.85         -> low
0.85 <= ratio < 1.00 -> moderate_low
1.00 <= ratio < 1.15 -> moderate
1.15 <= ratio < 1.30 -> high
ratio >= 1.30        -> very_high
```

Official probabilities per team evaluation are:

```text
band          goal   chance
low           0.12   0.20
moderate_low  0.20   0.28
moderate      0.26   0.35
high          0.36   0.45
very_high     0.46   0.55
```

The goal values were selected through a reproducible seeded 1,000-match
calibration comparison. `CHANCE` and `GOAL` are evaluated independently. One
block can produce at most one chance and one goal per team.

These values may change only through a separate approved calibration task.

## Domain Events

Only these domain event types exist:

```text
GOAL
CHANCE
TACTICAL_CHANGE
ENERGY_WARNING
```

- `GOAL` changes the score.
- `CHANCE` reports abstract attacking danger without a specific play.
- `TACTICAL_CHANGE` records a validated change from the previous tactic.
- `ENERGY_WARNING` records the approved low-energy threshold crossing.

No v0.2.0 interaction may create a second outcome event path.

Assists, cards, substitutions, goalkeeper saves, injuries, and fouls are not
implemented domain mechanics or event types. Presentation text must not imply
that they have been resolved.

## Presentation Events

The Match Engine evaluates each block once. The presentation layer then reveals
the finalized result over display time. Presentation-only pressure, momentum,
tempo, reaction, dominance, late-push, and quiet-match messages are narrative
and are not domain event types.

Presentation timing uses the match seed and variable gaps, generally around
5-12 displayed minutes. If 15 displayed minutes pass with no visible entry, a
`QUIET_MATCH` message resets display inactivity without changing game state.

The presentation timeline also marks the fixed lifecycle boundaries: kickoff,
both hydration breaks, both resumptions, half-time, the second-half start, and
full-time. These deterministic markers are web presentation entries rather than
domain events and cannot modify MatchState or simulation results.

Narration classifies display time as:

```text
EARLY          1-30
MID            31-70
LATE           71-90
STOPPAGE_TIME  added time after 45 or 90
```

It may also classify a team as winning, drawing, or losing to avoid
contradictory messages. These classifications remain presentation-only.

The visual layer shows team selection, recommendations, validated human choices,
and a simple horizontal 2D field. The field uses team markers, a ball marker,
and predefined patterns for neutral play, attacking pressure, chances, and
goals. These patterns consume resolved timeline events and do not represent
possession, passes, physics, collisions, autonomous player behavior, or a
second simulation. The visualizer must not calculate outcomes or invoke an
agent during playback.

Before kickoff, both teams use a coherent presentation-only 4-3-3 marker
layout entirely within their own halves. During playback, neutral movement is
subtle, pressure advances one side while the other retreats and compacts,
chances move toward the defending penalty area, and goals end at the goal area
with a short emphasis. None of these movements changes team ordering or match
state.

## Break Behavior

The browser pauses at breaks by default. If `Pause at breaks` is disabled, a
15-second browser countdown invokes the existing continue action. There are no
backend timers. Full time never restarts automatically. Desktop layout space
for the countdown and contextual break controls is reserved whether those
controls are active or not, so phase changes do not resize the match surface.

## Provider Failure and Validation

AI responses are untrusted. Pydantic validates structured fields and allowed
enum values. Missing configuration, provider failures, empty responses, and
malformed output use deterministic fallback behavior.

Provider credentials, authorization headers, raw reasoning, and full payloads
must not enter prompts exposed to users, MatchState, events, or logs.

## Calibration Diagnostics

`scripts/calibrate_matches.py` runs the existing match flow over seeds `1..N`
using local fallback decisions, no browser playback, no delays, and no Groq
calls. It measures outcomes without changing production values.

## Scope Boundary

`CURRENT_SCOPE.md` is authoritative for approved development. Items in
`IDEA_BACKLOG.md` are candidates only and must not be inferred from this game
specification.
