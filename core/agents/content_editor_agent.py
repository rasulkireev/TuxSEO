from pydantic_ai import Agent

from core.agents.system_prompts import (
    add_language_specification,
    add_project_details,
    add_project_pages,
    add_target_keywords,
    add_title_details,
    inline_link_formatting,
)
from core.choices import get_default_ai_model
from core.schemas import BlogPostGenerationContext

agent = Agent(
    get_default_ai_model(),
    output_type=str,
    deps_type=BlogPostGenerationContext,
    system_prompt="""
    You are an expert content editor.

    Your task is to edit the blog post content based on the requested changes.
    """,
    retries=2,
    model_settings={"temperature": 0.3},
)


@agent.system_prompt
def only_return_the_edited_content() -> str:
    return """
        IMPORTANT: Only return the edited content, no other text.
    """


agent.system_prompt(add_project_details)
agent.system_prompt(add_project_pages)
agent.system_prompt(add_title_details)
agent.system_prompt(add_language_specification)
agent.system_prompt(add_target_keywords)
agent.system_prompt(inline_link_formatting)
