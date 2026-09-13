# PRD.md

## Product

AI Football — v0.1.0

## Goal

Build a small browser-based agentic football match between two fictional teams.

The game must feel like a simple Elifoot-style probabilistic simulation, not a detailed football simulator.

The main objective is to demonstrate a practical multi-agent AI system using Python and Groq while keeping the project small enough to finish and publish.

## User

The user acts as the `Human Manager`.

In v0.1.0, the Human Manager:

* starts the match;
* observes the simulation;
* reviews match state between blocks;
* clicks `Continue` to advance the match.

The Human Manager does not make tactical changes or substitutions in v0.1.0.

## Match Structure

One match only.

Two fictional teams.

Four simulation blocks:

1. 1'–25'
2. 26'–45'+5
3. 46'–70'
4. 71'–90'+5

Pauses:

* hydration break after 25';
* half-time after first half;
* hydration break after 70';
* full-time after final block.

## Core Experience

The user should be able to:

1. Open the application in a browser.
2. See two fictional teams.
3. Start the match.
4. Watch match events appear.
5. See the score and energy change.
6. Observe tactical and Footballer decisions indirectly through events/state.
7. Continue through each match block.
8. See the final score.
9. See AI usage statistics:

   * API calls;
   * input tokens;
   * output tokens;
   * total tokens;
   * estimated cost.

## Success Criteria

v0.1.0 is complete when:

* a complete 90'+ match can run from start to finish;
* Coach Agents influence tactics;
* Footballers influence team performance;
* Match Engine resolves outcomes probabilistically;
* energy affects performance;
* randomness allows plausible unexpected results;
* Groq usage is tracked;
* the browser shows a clear visual match experience;
* automated tests pass;
* the project can be published publicly.

## Explicitly Out of Scope

v0.1.0 does not include:

* leagues;
* championships;
* multiple selectable teams;
* real teams;
* real players;
* historical football datasets;
* transfers;
* contracts;
* finances;
* scouting;
* training;
* bench players;
* substitutions;
* injuries;
* cards;
* fouls;
* penalties;
* offsides;
* corners;
* explicit shots;
* explicit passes;
* dribbling;
* tackles;
* ball possession by individual Footballers;
* field coordinates;
* physics;
* agent-to-agent free conversation;
* RAG;
* vector databases;
* local LLMs;
* authentication;
* multiplayer;
* save games;
* LLM-as-a-judge;
* complex agent graphs.

## Future Direction

After v0.1.0 is validated publicly, future versions may explore:

* multiple teams;
* championships;
* historical ratings;
* Elo-style rankings;
* substitutions;
* human tactical intervention;
* explicit ball possession;
* Footballer-to-Footballer interaction;
* richer multi-agent orchestration;
* free agent communication;
* RAG-based agent discovery;
* multilingual UI.
