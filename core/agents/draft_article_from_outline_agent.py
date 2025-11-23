from pydantic_ai import Agent

from core.agents.schemas import ArticleDraftContext, GeneratedBlogPostSchema
from core.agents.system_prompts import (
    add_language_specification,
    add_outline_context,
    add_project_details,
    add_project_pages,
    add_target_keywords_for_article,
    add_title_details,
    add_todays_date,
    article_from_outline_guidelines,
    filler_content,
    markdown_lists,
    post_structure,
    valid_markdown_format,
)
from core.choices import ContentType, get_default_ai_model
from core.prompts import GENERATE_CONTENT_SYSTEM_PROMPTS

ARTICLE_DRAFTING_BASE_PROMPT = """
You are an expert content writer specializing in transforming structured outlines into complete, engaging articles.

PHASE 2: ARTICLE DRAFTING

Your task is to:
1. Follow the provided outline structure EXACTLY
2. Expand each section with comprehensive, valuable content
3. Distribute the provided keywords naturally and evenly throughout the ENTIRE article
4. Maintain a clear, informative, and coherent tone throughout
5. Ensure every paragraph adds value to the reader

KEY RESPONSIBILITIES:
- Transform outline sections into full ## headings with detailed content
- Start with a compelling introduction (no heading)
- Distribute keywords from introduction through conclusion
- Ensure no section is overloaded with keywords
- Maintain natural flow and readability at all times
- Create content that is both human-friendly and search-engine optimized

CRITICAL REQUIREMENTS:
- Follow the outline structure strictly - do not add or remove sections
- Distribute keywords evenly across all sections
- Never sacrifice readability for keyword placement
- Avoid filler content, repetition, and placeholders
- Keep formatting clean and consistent
"""


def create_draft_article_from_outline_agent(
    content_type: ContentType = ContentType.SHARING, model=None
):
    """
    Create an agent to draft complete articles from outlines.

    Args:
        content_type: The type of content to generate (SHARING, ACTIONABLE, THOUGHT_LEADERSHIP).
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance for article drafting
    """
    base_content_prompt = GENERATE_CONTENT_SYSTEM_PROMPTS.get(
        content_type, GENERATE_CONTENT_SYSTEM_PROMPTS[ContentType.SHARING]
    )

    combined_prompt = f"{ARTICLE_DRAFTING_BASE_PROMPT}\n\n{base_content_prompt}"

    agent = Agent(
        model or get_default_ai_model(),
        output_type=GeneratedBlogPostSchema,
        deps_type=ArticleDraftContext,
        system_prompt=combined_prompt,
        retries=2,
        model_settings={"max_tokens": 65500, "temperature": 0.8},
    )

    agent.system_prompt(add_project_details)
    agent.system_prompt(add_project_pages)
    agent.system_prompt(add_title_details)
    agent.system_prompt(add_todays_date)
    agent.system_prompt(add_language_specification)
    agent.system_prompt(add_outline_context)
    agent.system_prompt(add_target_keywords_for_article)
    agent.system_prompt(article_from_outline_guidelines)
    agent.system_prompt(valid_markdown_format)
    agent.system_prompt(markdown_lists)
    agent.system_prompt(post_structure)
    agent.system_prompt(filler_content)

    return agent
