from pydantic_ai import Agent, RunContext

from core.choices import get_default_ai_model
from core.schemas import CompetitorDetails, WebPageContent


def create_populate_competitor_details_agent(model=None):
    """
    Create an agent to extract and populate competitor details from webpage content.

    Args:
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=CompetitorDetails,
        deps_type=WebPageContent,
        system_prompt=(
            """
            You are an expert marketer.
            Based on the competitor details and homepage content provided,
            extract and infer the requested information. Make reasonable inferences based
            on available content, context, and industry knowledge.
            """
        ),
        retries=2,
    )

    @agent.system_prompt
    def add_webpage_content(ctx: RunContext[WebPageContent]) -> str:
        return f"Content: {ctx.deps.markdown_content}"

    return agent
