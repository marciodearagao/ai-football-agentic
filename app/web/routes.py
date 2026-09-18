from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict

from app.domain.enums import TeamTactic
from app.match.match_controller import InvalidMatchTransition
from app.version import APP_VERSION
from app.web.session import TeamSide, WebMatchSession

router = APIRouter()


class TeamSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    side: TeamSide


class HumanTacticRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tactic: TeamTactic


def _session(request: Request) -> WebMatchSession:
    return request.app.state.match_session


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"version": APP_VERSION},
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


@router.post("/api/match/select-team")
def select_team(
    selection: TeamSelectionRequest,
    request: Request,
) -> dict[str, object]:
    try:
        return _session(request).select_team(selection.side)
    except InvalidMatchTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post("/api/match/human-tactic")
def set_human_tactic(
    selection: HumanTacticRequest,
    request: Request,
) -> dict[str, object]:
    try:
        return _session(request).set_human_tactic(selection.tactic)
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
