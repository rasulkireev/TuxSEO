from pydantic_ai import Agent

from core.agents.system_prompts import add_webpage_content
from core.choices import get_default_ai_model
from core.schemas import ProjectDetails, WebPageContent


def create_analyze_project_agent(model=None):
    """
    Create an agent to analyze project content and extract key information.

    Args:
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=ProjectDetails,
        deps_type=WebPageContent,
        system_prompt=(
            "You are an expert content analyzer. Based on the content provided, "
            "extract and infer the requested information. Make reasonable inferences based "
            "on available content, context, and industry knowledge."
        ),
        retries=2,
    )
    agent.system_prompt(add_webpage_content)

    return agent
