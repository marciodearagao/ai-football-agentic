# Current Scope

Version: 0.2.0  
Status: Release ready  
Branch: dev

This file records the approved v0.2.0 release boundary and completion state.

## Implemented in v0.2.0

- Team Selection: the Human Manager must select one of the two existing teams
  before kickoff; the other team becomes the opponent for that in-memory match.
- Coaching roles: the Human Manager chooses the selected team's tactic, the AI
  Assistant only recommends, and the other team's CoachAgent acts autonomously.
- Read-only LLM tool calling: both coaches may choose among five bounded match
  state lookups before returning a validated tactic or recommendation.
- Provider fallback: AssistantCoach and the opponent CoachAgent try Groq first,
  then Gemini, then their deterministic fallback.
- Simple 2D Match Visualizer: an isolated SVG component animates predefined
  patterns from already resolved presentation events.
- Design system and full-screen match UX: the live browser view uses a compact
  viewport shell and presentation-only directional animation targets.
- Final match UX refinement: setup and break layouts remain stable, the header
  reports runtime provider use, and the feed includes lifecycle milestones.
- Laptop UX refinement: medium desktop screens prioritize the field, while the
  release runtime is visibly identified as `v0.2.0`.
- Laptop pitch scaling and provider clarity: the medium layout preserves the
  SVG field ratio, and local startup reports provider availability safely.
- Match Center refinement: short desktop viewports use a compact, height-aware
  presentation geometry without changing match behavior.

## In Scope

- Human Manager
- Team Selection
- AI Assistant Coach
- AI Opponent Coach
- LLM Tool / Function Calling
- Human-in-the-loop tactic decision
- Simple visual match presentation

## Out of Scope

- championships
- leagues
- standings
- real teams
- real historical datasets
- transfers
- substitutions
- persistence
- LangGraph
- Agent Memory
- MCP
- RAG
- vector databases
- Reinforcement Learning
- detailed ball physics
- collision-based goals
- autonomous visual players
- second Match Engine

## Non-negotiable Rules

- The Match Engine remains the authority for match outcomes.
- The visual layer only presents already resolved state and events.
- The Human Manager controls one team.
- The AI Assistant recommends; the Human Manager decides.
- The AI Opponent Coach remains autonomous.
- No future technology is introduced unless explicitly approved.
