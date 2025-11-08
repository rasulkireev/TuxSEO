from pydantic_ai import Agent

from core.agents.system_prompts import (
    add_language_specification,
    add_project_details,
    add_project_pages,
    add_target_keywords,
    add_title_details,
)
from core.choices import get_default_ai_model
from core.schemas import BlogPostGenerationContext, BlogPostStructure

agent = Agent(
    get_default_ai_model(),
    output_type=BlogPostStructure,
    deps_type=BlogPostGenerationContext,
    system_prompt="""
    You are an expert content strategist and SEO specialist.

    Your task is to create a comprehensive, well-structured outline for a blog post.
    Think deeply about:

    1. **Logical Flow**: How should information be presented for maximum clarity and impact?
    2. **SEO Optimization**: What headings and structure will rank well in search engines?
    3. **User Intent**: What questions does the reader have, and in what order should they be answered?
    4. **Comprehensiveness**: What topics must be covered for this to be a complete resource?
    5. **Readability**: How can we break down complex topics into digestible sections?

    Consider the project details, title suggestion, and available project pages when creating the structure.
    The structure should be detailed enough that a writer can follow it to create excellent content.

    Important guidelines:
    - Use H2 (level 2) for main sections
    - Use H3 (level 3) for subsections within main sections
    - Aim for 5-8 main sections (H2) for a comprehensive post
    - Each section should have 3-5 key points to cover
    - Target 2000-3000 total words for the post
    - Include specific guidance for introduction and conclusion
    """,  # noqa: E501
    retries=2,
    model_settings={"temperature": 0.7},
)

agent.system_prompt(add_project_details)
agent.system_prompt(add_project_pages)
agent.system_prompt(add_title_details)
agent.system_prompt(add_language_specification)
agent.system_prompt(add_target_keywords)
