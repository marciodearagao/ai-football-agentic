from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.web.routes import router
from app.web.session import WebMatchSession

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(match_session: WebMatchSession | None = None) -> FastAPI:
    load_dotenv(PROJECT_ROOT / ".env")
    application = FastAPI(title="AI Football Agentic", version="0.1.0")
    application.state.match_session = match_session or WebMatchSession()
    application.state.templates = Jinja2Templates(
        directory=str(PROJECT_ROOT / "templates")
    )
    application.mount(
        "/static",
        StaticFiles(directory=str(PROJECT_ROOT / "static")),
        name="static",
    )
    application.include_router(router)
    return application


app = create_app()
