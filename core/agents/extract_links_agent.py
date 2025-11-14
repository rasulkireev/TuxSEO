from pydantic_ai import Agent, RunContext

from core.agents.models import get_default_ai_model


def create_extract_links_agent(model=None):
    """
    Create an agent to extract URLs from markdown-formatted text.

    Args:
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=list[str],
        deps_type=str,
        system_prompt="""
            You are an expert link extractor.
            Extract all the URLs from the markdown-formatted text provided.
            Return only valid, complete URLs (starting with http:// or https://).
            If the text contains no valid URLs, return an empty list.
        """,
        retries=2,
        model_settings={"temperature": 0.2, "thinking_budget": 0},
    )

    @agent.system_prompt
    def add_links_text(ctx: RunContext[str]) -> str:
        return f"Markdown text containing links:\n{ctx.deps}"

    return agent
