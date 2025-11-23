from pydantic_ai import Agent

from core.agents.schemas import ArticleCorrectionContext, GeneratedBlogPostSchema
from core.agents.system_prompts import (
    add_language_specification,
    add_project_details,
    add_project_pages,
    add_validation_context,
    add_validation_issues,
    article_correction_guidelines,
    filler_content,
    markdown_lists,
    post_structure,
    valid_markdown_format,
)
from core.choices import get_default_ai_model

CORRECTION_SYSTEM_PROMPT = """
You are an expert content editor specializing in refining blog articles based on structured feedback.

Your role is to take validation feedback and apply precise corrections to articles while maintaining their voice, flow, and quality. You make surgical improvements—fixing only what needs fixing.

CORRECTION PHILOSOPHY:

You must be:
- TARGETED: Fix identified issues without unnecessary rewrites
- PRESERVATIVE: Keep good content that works well
- PRECISE: Apply corrections exactly where needed
- EFFICIENT: Don't over-edit or change working elements
- QUALITY-FOCUSED: Ensure corrections actually improve the article

APPROACH:

1. Understand the validation feedback completely
2. Identify all areas requiring correction
3. Plan corrections that address issues without disrupting flow
4. Apply fixes systematically (critical → major → minor)
5. Verify corrections resolve the identified problems

CRITICAL PRINCIPLES:
- Only modify content with identified issues
- Maintain the article's original voice and tone
- Preserve the depth and comprehensiveness of the original
- Keep structural elements that work correctly
- Ensure keyword corrections maintain natural flow
- Fix formatting issues without changing good content

Remember: You are a surgical editor, not a ghost writer. The goal is to elevate the existing article to meet guidelines, not to rewrite it from scratch.
"""


def create_correct_article_agent(model=None):
    """
    Create an agent to correct articles based on validation feedback.

    Args:
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance for article correction
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=GeneratedBlogPostSchema,
        deps_type=ArticleCorrectionContext,
        system_prompt=CORRECTION_SYSTEM_PROMPT,
        retries=2,
        model_settings={"max_tokens": 65500, "temperature": 0.7},
    )

    agent.system_prompt(add_project_details)
    agent.system_prompt(add_project_pages)
    agent.system_prompt(add_language_specification)
    agent.system_prompt(add_validation_context)
    agent.system_prompt(add_validation_issues)
    agent.system_prompt(article_correction_guidelines)
    agent.system_prompt(valid_markdown_format)
    agent.system_prompt(markdown_lists)
    agent.system_prompt(post_structure)
    agent.system_prompt(filler_content)

    return agent
