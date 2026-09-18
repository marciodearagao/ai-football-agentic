import os
import sys
import webbrowser
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn
from dotenv import load_dotenv

from app.version import APP_VERSION

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"
PROJECT_ROOT = Path(__file__).resolve().parent


def _provider_configuration_summary() -> tuple[str, str]:
    """Return non-sensitive local provider availability labels."""
    groq_configured = bool(os.getenv("GROQ_API_KEY", "").strip())
    gemini_configured = bool(os.getenv("GEMINI_API_KEY", "").strip())
    return (
        f"Groq: {'configured' if groq_configured else 'not configured'}",
        "Gemini fallback: "
        f"{'configured' if gemini_configured else 'not configured'}",
    )


def _open_browser_when_ready(server: uvicorn.Server, timeout: float = 15.0) -> None:
    deadline = monotonic() + timeout
    state_url = f"{URL}/api/match/state"
    while monotonic() < deadline and not server.should_exit:
        if server.started:
            try:
                with urlopen(state_url, timeout=0.5) as response:
                    if response.status == 200:
                        print(f"Server ready: {URL}")
                        print("Opening browser...\n")
                        print("Press Ctrl+C to stop.")
                        webbrowser.open(URL)
                        return
            except (OSError, URLError):
                pass
        sleep(0.1)


def main() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    load_dotenv(PROJECT_ROOT / ".env")
    print(f"AI Football Agentic v{APP_VERSION}\n")
    for provider_status in _provider_configuration_summary():
        print(provider_status)
    print()
    print("Starting server...")
    config = uvicorn.Config(
        "app.main:app",
        host=HOST,
        port=PORT,
        log_level="error",
        access_log=False,
    )
    server = uvicorn.Server(config)
    browser_thread = Thread(
        target=_open_browser_when_ready,
        args=(server,),
        daemon=True,
    )
    browser_thread.start()
    try:
        server.run()
    except KeyboardInterrupt:
        server.should_exit = True
    finally:
        print("\nStopping server...")
        print("Server stopped.")


if __name__ == "__main__":
    main()
