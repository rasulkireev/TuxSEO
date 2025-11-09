from pydantic_ai import Agent

from core.agents.schemas import ProjectPageDetails, WebPageContent
from core.agents.system_prompts import add_webpage_content
from core.choices import get_default_ai_model


def create_summarize_page_agent(model=None):
    """
    Create an agent to summarize web page content.

    Args:
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=ProjectPageDetails,
        deps_type=WebPageContent,
        system_prompt=(
            "You are an expert content summarizer. Based on the web page content provided, "
            "create a concise 2-3 sentence summary that captures the main purpose and key "
            "information of the page. Focus on what the page is about and its main value proposition."  # noqa: E501
        ),
        retries=2,
        model_settings={"temperature": 0.5},
    )
    agent.system_prompt(add_webpage_content)

    return agent
