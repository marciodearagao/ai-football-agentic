# AI Football Agentic

AI Football Agentic is a small browser-based agentic football simulation
inspired by classic management games. Its Match Engine is intentionally
probabilistic: agents choose tactics and behavior, while the engine resolves
chances, goals, energy changes, and the final result.

It is a compact demonstration, not a realistic football simulator.

## Current version

**Current version: 0.1.0**

Version 0.1.0 contains one standalone match between two fictional teams,
agentic Coach and Footballer decisions, four simulation blocks presented over
approximately four minutes, and in-memory AI token and cost tracking.

## Architecture

```text
Human Manager
      ↓
Web UI / FastAPI
      ↓
Match Controller
      ↓
Coach / Footballer decisions
      ↓
Match Engine
      ↓
Presentation layer
```

Agents choose behavior. The Match Engine resolves consequences.

Each team has one CoachAgent and one CognitiveFootballer powered by Groq. The
other ten Footballers use deterministic ReactiveFootballer or
TacticalFootballer logic. Across four blocks, the theoretical maximum is 16
Groq calls: eight Coach decisions and eight CognitiveFootballer decisions.
Invalid, unavailable, or unconfigured AI responses use deterministic fallback
logic, so the match remains playable without successful provider calls.

See [GAME_SPEC.md](docs/GAME_SPEC.md) for the technical game rules and
[ARCHITECTURE.md](docs/ARCHITECTURE.md) for component responsibilities.

## Groq integration

The current model is `qwen/qwen3.8-27b`. Requests use:

```python
response_format={"type": "json_object"}
reasoning_format="hidden"
```

Prompts require a single JSON object. Pydantic validates the exact fields and
allowed enum values before a decision can affect the match; rejected responses
fall back to deterministic Python logic.

The UI tracks API calls, input tokens, output tokens, total tokens, cached tokens
when available, and estimated cost. Estimated cost is calculated from configured
model pricing and is not an authoritative billing invoice.

A manual live-match example used 16 calls, about 4.8K tokens, and approximately
$0.005. Actual usage and cost vary by match and provider output.

## Match Engine

The Match Engine combines high-level team skill, energy, tactics, Footballer
behavior, and controlled randomness. Agents influence these inputs but never
directly select goals or results.

The v0.1.0 goal model was calibrated using repeated 1,000-match seeded
simulations rather than tuning from individual matches.

## Setup

Python 3.12 or newer is required. From Bash or Git Bash on Windows:

```bash
git clone <repository-url>
cd ai-football-agentic

python -m venv .venv
source .venv/Scripts/activate
pip install -e .

cp .env.example .env
```

On Linux or macOS, activate the environment with:

```bash
source .venv/bin/activate
```

Configure `.env` as needed:

```text
GROQ_API_KEY=
GROQ_MODEL=qwen/qwen3.8-27b
```

Groq configuration is optional. Without it, deterministic fallbacks run the
complete match and report no provider token usage.

## Run

```bash
python run.py
```

The launcher starts the local FastAPI server, opens
`http://127.0.0.1:8000` in the default browser, and stops cleanly with
`Ctrl+C`.

## Tests and calibration

Install the development dependency and run the suite:

```bash
pip install -e '.[dev]'
pytest
```

Run the reproducible, provider-free calibration diagnostic with:

```bash
python scripts/calibrate_matches.py 1000
```

## Screenshots

Release screenshots can be placed in `docs/images/` as `match-start.png`,
`match-live.png`, and `match-full-time.png`. They are not linked here until real
captures are available.

## Known limitations

- Two fictional teams and one standalone match only.
- No substitutions, bench, leagues, championships, or persistence.
- No real football data.
- No individual ball, pass, shot, tackle, or positional simulation.
- English-only UI.
- Agents do not communicate freely with each other.

## Future direction

Possible future work includes more teams and championships, substitutions and
team management, historical ratings, richer agent interactions, and explicit
ball or possession simulation. These are not part of v0.1.0.
