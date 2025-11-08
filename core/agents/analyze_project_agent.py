from pydantic_ai import Agent

from core.agents.system_prompts import (
    add_webpage_content,
)
from core.choices import get_default_ai_model
from core.schemas import (
    ProjectDetails,
    WebPageContent,
)

agent = Agent(
    get_default_ai_model(),
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
