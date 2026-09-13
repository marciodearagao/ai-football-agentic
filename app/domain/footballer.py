from pydantic import BaseModel, Field

from app.domain.enums import FootballerBehavior


class Footballer(BaseModel):
    name: str
    skill: float = Field(ge=0, le=100)
    intelligence: float = Field(ge=0, le=100)
    stamina: float = Field(ge=0, le=100)
    energy: float = Field(default=100, ge=0, le=100)
    behavior: FootballerBehavior = FootballerBehavior.SUPPORT
