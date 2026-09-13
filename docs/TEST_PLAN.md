# TEST_PLAN.md

## Objective

Verify that v0.1.0 behaves consistently, plausibly and safely without attempting to prove realistic football simulation.

## Unit Tests

### Footballer

Verify:

* valid attributes;
* energy decreases correctly;
* energy never becomes invalid;
* stamina affects energy consumption;
* valid behaviors only.

### Footballer Decision Logic

Verify:

* ReactiveFootballer follows rules;
* TacticalFootballer uses expected context;
* invalid behavior is rejected;
* fallback behavior works.

CognitiveFootballer tests should mock Groq.

### Coach Agent

Verify:

* only valid tactics accepted;
* malformed AI output rejected;
* fallback tactic works;
* structured output validated.

### Match Engine

Verify:

* team strength calculated correctly;
* energy modifiers applied;
* tactical modifiers applied;
* behavior modifiers applied;
* randomness stays inside configured boundaries;
* goals correctly change score.

### Random Seed

Verify:

```text
same inputs + same seed
=
same simulation result
```

## Match Flow Tests

Verify correct sequence:

```text
START
→ 25
→ hydration
→ 45+5
→ half-time
→ 70
→ hydration
→ 90+5
→ full-time
```

Verify that the Human Manager cannot accidentally skip invalid phases.

## Event Tests

Only these event types should be accepted:

```text
GOAL
CHANCE
TACTICAL_CHANGE
ENERGY_WARNING
```

Unsupported event types must not appear.

## Usage Tracking Tests

Using mocked Groq responses, verify:

* API calls counted;
* input tokens accumulated;
* output tokens accumulated;
* total tokens calculated;
* usage separated by agent;
* estimated cost calculated correctly when pricing exists;
* application works when pricing is unavailable.

## Plausibility Tests

Run repeated simulations to inspect whether:

* stronger teams tend to perform better;
* weaker teams can still win sometimes;
* ATTACK increases attacking potential;
* DEFEND increases defensive protection;
* low energy reduces performance;
* randomness does not completely dominate skill.

These are calibration tests rather than strict realism tests.

## Scope Protection Tests / Review

Before completing each implementation milestone, verify that no feature has introduced:

* passes;
* shots;
* tackles;
* ball possession;
* substitutions;
* injuries;
* cards;
* free agent communication;
* championships;
* real datasets.

If implementation requires one of those features, stop and treat it as future scope instead of silently expanding v0.1.0.

## Definition of Done

v0.1.0 is ready for GitHub when:

* application starts locally;
* full match completes;
* browser UI works;
* agents affect simulation;
* Groq failures have safe fallback;
* token usage is visible;
* tests pass;
* `.env` secrets are excluded;
* README explains setup and architecture;
* no explicit OUT/FUTURE feature has entered the implementation.

## Dependency warnings

The v0.1.0 test run may report two deprecation warnings originating inside the
installed FastAPI/Starlette test-client compatibility layer. Project code does
not call the deprecated APIs. Dependency upgrades are intentionally deferred
because the warnings do not affect runtime behavior or test results.
