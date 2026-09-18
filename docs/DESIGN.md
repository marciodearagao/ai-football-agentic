# Design System

This file defines the persistent visual direction for the project. Read it
before changing the browser UI.

## Product Identity

- Retro football manager with modern usability.
- Game-first, not SaaS-dashboard-first.
- Compact and information-dense.
- Preserve the dark green and cream identity where practical.
- Monospace and technical accents may be used for match data.

## Layout

- The browser UI has two explicit modes. Management Mode is the compact
  pre-match workspace for team selection, matchup, tactic, Assistant Coach
  recommendation, provider status, and kickoff. It does not display the live
  pitch.
- Starting the match opens a dedicated foreground Match Center. The management
  workspace remains inactive behind it, and the Match Center stays open through
  live play, hydration breaks, half-time, and full-time.
- The Match Center contains the score and clock, pitch, events, decisions,
  timeline, match data, Human Manager controls, and break/full-time actions.
  Starting a new match closes it and returns to a fresh Management Mode.
- Use the available desktop viewport and prefer a full-width application shell.
- Minimize routine vertical scrolling during live play.
- Keep the wide-desktop shell height stable from setup through full-time;
  reserve space for contextual controls instead of resizing the match surface.
- Keep score, clock, field, events, decisions, tactics, energy, and essential
  controls visible together when reasonably possible.
- On medium desktop and laptop screens, prioritize field width by moving event
  and decision panels into a compact row below it; retain the side-by-side
  layout on wide monitors.
- On desktop screens with limited viewport height, use Compact Match Center:
  keep event and decision panels beside the pitch, size the pitch from the
  available match height, and keep controls within the fixed match surface.
- The pitch SVG must use the largest available box that preserves its `5 / 3`
  view-box ratio; never stretch the pitch or leave the actual field miniature
  inside an oversized green SVG viewport.
- When width is the constraint, pitch height may derive from available width.
  When height is the constraint, derive pitch width from the available height
  so the Match Center remains compact without distorting the pitch.
- Stack sections into a usable reading order on narrow screens.

## Visual Hierarchy

Use this priority order:

1. score and clock;
2. match field;
3. current event;
4. Human Manager controls;
5. Assistant Coach recommendation;
6. energy and secondary match information.

## Components

- Prefer compact panels with clear boundaries over oversized cards.
- Keep events readable at a glance.
- Do not add decoration that reduces usable match space.
- Inactive contextual controls may remain visually hidden in reserved grid
  areas on desktop; narrow layouts may remove that reserved space when stacked.

## Match Visualization

- The pitch is rendered only inside the Match Center; Management Mode does not
  create a second visualizer.
- Starting formations are initial visual anchors, not movement boundaries.
- Players may cross midfield during attacking states.
- Pressure and chance patterns should put multiple players in the opponent half
  or final third.
- Movement is predefined and presentation-only.
- The visualizer never determines match state or outcomes.

## Future Compatibility

The layout may eventually support navigation concepts such as Match, Fixtures,
Table, and Team. These are compatibility considerations, not approved features;
do not render unavailable sections or present them as a committed roadmap.
