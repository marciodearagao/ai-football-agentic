from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.domain.enums import TeamTactic
from app.domain.footballer import Footballer


class Team(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    footballers: list[Footballer] = Field(min_length=11, max_length=11)
    tactic: TeamTactic = TeamTactic.BALANCED

    @property
    def base_strength(self) -> float:
        return sum(footballer.skill for footballer in self.footballers) / len(
            self.footballers
        )
