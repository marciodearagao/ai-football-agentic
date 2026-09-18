# AI Football Agentic

AI Football Agentic is a small browser-based football simulation inspired by
classic management games. Agents choose tactics and abstract behavior, while a
probabilistic Match Engine remains authoritative over chances, goals, energy,
and the final result.

## Project status

`v0.2.0` is a standalone, local football-management simulation between two
fictional teams. Choose your team and tactic in Management Mode, then follow
the resolved match in the responsive Match Center.

The Human Manager controls one team's tactic. An AI Assistant Coach may
recommend a tactic, while the opposing CoachAgent remains autonomous. Coaching
uses validated, read-only match-context tools with Groq as primary provider,
Gemini as optional fallback, and deterministic local fallbacks when providers
are unavailable.

## Current architecture

```text
Web UI / FastAPI
        |
Match Controller
        |
Coach and Footballer decisions
        |
Authoritative Match Engine
        |
Presentation layer
```

The application uses Groq as the primary provider for structured AI Assistant,
opponent Coach, and CognitiveFootballer decisions.
Assistant and opponent coaching use Gemini as a single secondary provider when
Groq fails. Pydantic validates every final decision before it can affect the
simulation. If both providers fail, deterministic fallbacks keep the match
playable.

Assistant and opponent coaching use local function calling with both supported
providers. The application executes five read-only match-context tools and
returns their results to the selected model; these tools cannot mutate the
match or bypass the Human Manager.

The presentation layer reveals already resolved events. It does not calculate
goals, change probabilities, or run agent decisions during playback.
Its 2D field uses predefined SVG animation patterns and can be replaced without
changing the Match Engine, agents, or match orchestration. The Match Center
keeps the score, field, event feed, decisions, controls, runtime provider
status, and presentation-only lifecycle milestones together without changing
resolved match outcomes.

See [`docs/GAME_SPEC.md`](docs/GAME_SPEC.md) for game rules and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for component responsibilities.

## Technology stack

- Python 3.12+
- FastAPI
- Pydantic
- Groq SDK
- Google Gen AI SDK
- Jinja2
- HTML, CSS, and vanilla JavaScript
- pytest
- python-dotenv

## Setup

From Bash or Git Bash on Windows:

```bash
git clone <repository-url>
cd ai-football-agentic

python -m venv .venv
source .venv/Scripts/activate
python -m pip install -c constraints.txt -e .

cp .env.example .env
```

On Linux or macOS, activate the environment with:

```bash
source .venv/bin/activate
```

Set `GROQ_API_KEY` and `GROQ_MODEL` in the local `.env` for the primary
provider. Gemini is an optional secondary provider: set `GEMINI_API_KEY` to
enable it. `GEMINI_MODEL` is optional and defaults to
`gemini-3.1-flash-lite`. `.env` is ignored by Git. If Groq fails and Gemini is
unavailable or also fails, deterministic fallbacks keep the full match
playable.

## Run

```bash
python run.py
```

The launcher serves the application at `http://127.0.0.1:8000`, opens the
default browser, and stops with `Ctrl+C`.

## Tests and calibration

```bash
python -m pip install -c constraints.txt -e '.[dev]'
pytest
```

`pyproject.toml` and `constraints.txt` pin the direct dependency versions
validated for this release.

The provider-free seeded calibration diagnostic is available with:

```bash
python scripts/calibrate_matches.py 1000
```

## Current limitations

- Two fictional teams and one standalone match.
- No substitutions, competitions, persistence, or real football data.
- No individual passes, shots, tackles, positions, or ball physics.
- English-only interface.
- Local single-user application.
