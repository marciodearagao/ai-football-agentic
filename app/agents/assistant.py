from app.agents.coach import CoachAgent, CoachDecision
from app.agents.coach_context import CoachContext
from app.usage.models import AgentType, make_agent_id


ASSISTANT_SYSTEM_PROMPT = """\
You advise a human football manager in an abstract simulation.
Recommend exactly one tactic: ATTACK, BALANCED, or DEFEND.
Use the available read-only tools when you need current match information.
The human decides whether to use your recommendation.
Your recommendation never changes the team tactic or determines match outcomes.
Return one valid JSON object only, with exactly these fields:
The tactic value must be exactly "ATTACK", "BALANCED", or "DEFEND".
The reason must be plain text between 1 and 160 characters.
Example shape: {"tactic":"BALANCED","reason":"Keep the team balanced."}
Do not use Markdown, code fences, commentary, or extra fields."""


class AssistantCoach(CoachAgent):
    system_prompt = ASSISTANT_SYSTEM_PROMPT

    def recommend_tactic(self, context: CoachContext) -> CoachDecision:
        return super().choose_tactic(context)

    @property
    def agent_id(self) -> str:
        return make_agent_id(AgentType.ASSISTANT_COACH, self.team_name)
