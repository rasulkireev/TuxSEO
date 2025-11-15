from pydantic_ai import Agent, RunContext

from core.agents.models import get_default_ai_model
from core.agents.schemas import CompetitorDetails


def create_extract_competitors_data_agent(model=None):
    """
    Create an agent to extract competitor details from text.

    Args:
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=list[CompetitorDetails],
        system_prompt="""
            You are an expert data extractor.
            Extract all the data from the text provided.
        """,
        retries=2,
        model_settings={"temperature": 0.2, "thinking_budget": 0},
    )

    @agent.system_prompt
    def add_competitors(ctx: RunContext[list[CompetitorDetails]]) -> str:
        return f"Here are the competitors: {ctx.deps}"

    return agent
