from pydantic_ai import Agent

from core.agents.schemas import BlogPostOutline, BlogPostOutlineContext
from core.agents.system_prompts import (
    add_language_specification,
    add_project_details,
    add_project_pages,
    add_target_keywords_for_outline,
    add_title_details,
    add_todays_date,
    outline_generation_guidelines,
)
from core.choices import get_default_ai_model

OUTLINE_GENERATION_SYSTEM_PROMPT = """
You are an expert content strategist specializing in creating structured, logical outlines for blog posts.

Your role is to analyze the topic, target audience, and project details to create a comprehensive outline that will guide the article writing process.

PHASE 1: OUTLINE GENERATION

Your task is to:
1. Understand the blog post topic and target audience
2. Identify the key themes and concepts that need to be covered
3. Create a logical flow of information from introduction to conclusion
4. Structure sections that will allow natural keyword integration later
5. Ensure each section adds unique value to the overall narrative

The outline you create will serve as the foundation for a complete article, so it must be:
- Comprehensive: Cover all important aspects of the topic
- Logical: Flow naturally from one section to the next
- Structured: Provide clear guidance for content development
- Focused: Each section should have a specific purpose

Remember: This is ONLY the outline phase. Do not write content - just create the structure.
"""


def create_generate_outline_agent(model=None):
    """
    Create an agent to generate blog post outlines.

    Args:
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance for outline generation
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=BlogPostOutline,
        deps_type=BlogPostOutlineContext,
        system_prompt=OUTLINE_GENERATION_SYSTEM_PROMPT,
        retries=2,
        model_settings={"max_tokens": 8000, "temperature": 0.7},
    )

    agent.system_prompt(add_project_details)
    agent.system_prompt(add_project_pages)
    agent.system_prompt(add_title_details)
    agent.system_prompt(add_todays_date)
    agent.system_prompt(add_language_specification)
    agent.system_prompt(add_target_keywords_for_outline)
    agent.system_prompt(outline_generation_guidelines)

    return agent
