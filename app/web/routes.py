from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.match.match_controller import InvalidMatchTransition
from app.web.session import WebMatchSession

router = APIRouter()


def _session(request: Request) -> WebMatchSession:
    return request.app.state.match_session


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"version": "0.1.0"},
    )


@router.get("/api/match/state")
def match_state(request: Request) -> dict[str, object]:
    return _session(request).state_payload()


@router.post("/api/match/start")
def start_match(request: Request) -> dict[str, object]:
    try:
        return _session(request).start()
    except InvalidMatchTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post("/api/match/continue")
def continue_match(request: Request) -> dict[str, object]:
    try:
        return _session(request).continue_match()
    except InvalidMatchTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post("/api/match/reset")
def reset_match(request: Request) -> dict[str, object]:
    try:
        return _session(request).reset()
    except InvalidMatchTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
