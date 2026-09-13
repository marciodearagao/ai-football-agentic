# GAME_SPEC.md

## Core Principle

The game is a probabilistic football simulation.

Agents choose behavior.

The `Match Engine` determines consequences.

Agents never directly decide:

* goals;
* final scores;
* match outcomes.

## Footballer Attributes

Each Footballer has:

```text
skill
intelligence
stamina
energy
```

### Skill

Represents general football ability.

Used to calculate team strength.

### Intelligence

Determines how the Footballer's behavior is selected internally.

### Stamina

Represents durability.

Influences how quickly energy decreases.

### Energy

Dynamic match state.

Starts high and decreases during the match.

Lower energy reduces effective performance.

After each simulation block, energy consumption is calculated as:

```text
stamina_factor = 1.20 - (stamina / 250)
energy_loss = 12 × stamina_factor × behavior_factor
```

Behavior factors are `1.15` for `ATTACK`, `1.00` for `SUPPORT`, `1.20` for
`PRESS`, and `0.65` for `CONSERVE_ENERGY`. Energy is clamped to `0–100`, and
there is no recovery during pauses. An `ENERGY_WARNING` is generated only when
a Footballer crosses from energy `>= 40` to energy `< 40`.

## Internal Footballer Types

These names are internal only.

They must never be shown to the user.

### ReactiveFootballer

Decision method:

* simple Python rules;
* current state only;
* no meaningful memory.

### TacticalFootballer

Decision method:

* Python logic;
* considers more match context;
* may consider previous block.

### CognitiveFootballer

Decision method:

* Groq LLM;
* uses structured contextual reasoning;
* exactly one exists per team in v0.1.0;
* makes one decision before each block, for at most four calls per match;
* falls back to TacticalFootballer logic when configuration or output is invalid.

All Footballer types choose from the same behaviors.

## Footballer Behaviors

Allowed behaviors:

```text
ATTACK
SUPPORT
PRESS
CONSERVE_ENERGY
```

The behaviors are abstract.

They do not represent individual passes, shots, tackles or physical actions.

### ATTACK

Increases offensive contribution.

Consumes additional energy.

### SUPPORT

Provides a small balanced contribution.

### PRESS

Increases defensive pressure.

Consumes additional energy.

### CONSERVE_ENERGY

Reduces immediate contribution.

Reduces energy consumption.

## Team Tactics

Coach Agent chooses from:

```text
ATTACK
BALANCED
DEFEND
```

Each Coach chooses once before each simulation block using score, match phase,
current tactic, average energy, relative team strength, and the previous block
result. Responses are structured and validated. If Groq is unavailable or the
response is invalid, the current tactic is retained.

### ATTACK

Higher offensive potential.

Higher defensive exposure.

### BALANCED

Neutral modifier.

### DEFEND

Lower offensive potential.

Higher defensive protection.

## Base Team Strength

Initial model:

```text
base_team_strength =
average(skill of starting Footballers)
```

No positional weighting in v0.1.0.

## Effective Strength

The Match Engine calculates separate values for:

```text
effective_attack
effective_defense
```

Conceptually:

```text
base strength
× energy modifier
× tactic modifier
× Footballer behavior modifier
```

Randomness is then applied.

Initial values are calibration parameters, not permanent football rules.

## Energy Modifier

Initial calibration bands may follow approximately:

```text
90–100 → 1.00
75–89  → 0.97
60–74  → 0.92
40–59  → 0.85
<40    → 0.75
```

These values may change during testing.

## Tactical Modifiers

Initial example:

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

These values remain configurable.

## Behavior Modifiers

Behavior effects remain small and are aggregated at team level. Each Footballer
adds the following adjustment:

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

The adjustments from all 11 Footballers are summed separately for attack and
defense, then each total is capped to the range `-10%` to `+10%`. This step uses
current behavior only and does not consume energy.

## Randomness

The engine applies controlled randomness.

Initial range:

```text
0.90–1.10
```

The purpose is to allow unexpected results without making team strength meaningless.

## Goal Probability

Goal probability depends primarily on:

```text
attacking team's effective_attack
vs
defending team's effective_defense
```

Higher ratios increase probability. The initial calibration is:

```text
ratio < 0.85        → low
0.85 ≤ ratio < 1.00 → moderate_low
1.00 ≤ ratio < 1.15 → moderate
1.15 ≤ ratio < 1.30 → high
ratio ≥ 1.30        → very_high
```

Goal and chance probabilities per team evaluation are:

```text
band          goal   chance
low           0.12   0.20
moderate_low  0.20   0.28
moderate      0.26   0.35
high          0.36   0.45
very_high     0.46   0.55
```

The v0.1.0 goal values were selected through a reproducible 1,000-match seeded
calibration comparison, rather than tuning from individual manual matches.

`CHANCE` and `GOAL` are evaluated independently. One block can produce at most
one of each result per team. These values remain calibration parameters.

## Match Events

The Match Engine evaluates each block once. The browser progressively presents
the finalized block result; it does not simulate match minutes on the backend.

Game events belong to the simulation and use only the approved types below. A
seeded presentation timeline may additionally show generic pressure, momentum,
tempo, or quiet-period narration. These presentation-only entries have no game
effect and do not introduce new domain event types or football mechanics.

If 15 displayed match minutes pass without any visible feed entry, the seeded
presentation timeline adds a light `QUIET_MATCH` message. It resets the display
inactivity count but has no effect on MatchState or simulation outcomes.

Normal narrative moments follow a continuous seeded schedule with variable
gaps, generally around 5–12 displayed minutes. Their templates use the score at
the reveal timestamp and classify time as early (1–30), middle (31–70), late
(71–90), or stoppage time. Winning, drawing, and losing context prevents obvious
contradictions such as early urgency or a losing team protecting a lead.

The developer calibration runner measures match outcomes over deterministic
seeds without Groq, browser playback, or delays. Its output is observational;
the probability bands, randomness, energy and tactical modifiers, behavior
modifiers, and one-goal-per-team-per-block limit remain unchanged in this step.

The browser pauses at hydration breaks and half-time by default. The user may
disable `Pause at breaks`; each break then remains visible with a 15-second
countdown before the normal next block begins. Full time never restarts
automatically. A disabled `MANAGE TEAM` control shown at breaks is future-only
and provides no management capability in v0.1.0.

Only four event types exist in v0.1.0:

```text
GOAL
CHANCE
TACTICAL_CHANGE
ENERGY_WARNING
```

### GOAL

Changes the score.

### CHANCE

Indicates attacking danger without modeling a specific shot or play.

### TACTICAL_CHANGE

Records a Coach Agent tactical decision.

Generated only when a validated Coach decision differs from the team's previous
tactic. It records the previous and new tactic as structured values.

### ENERGY_WARNING

Generated when relevant low-energy thresholds are reached.

## Random Seed

The Match Engine must support an optional random seed.

Purpose:

* reproducible tests;
* debugging;
* simulation comparison.

Normal gameplay may use a random seed automatically. The complete match flow
uses one seeded Match Engine across all four blocks, making outcomes, event
order, and final energy reproducible from identical initial state.
