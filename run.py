from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen
import sys
import webbrowser

import uvicorn

VERSION = "0.1.0"
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"
PROJECT_ROOT = Path(__file__).resolve().parent


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
    print(f"AI Football Agentic v{VERSION}\n")
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
