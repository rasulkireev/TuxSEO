from pydantic import BaseModel
from pydantic_ai import Agent

from core.choices import get_default_ai_model


class BlogPostValidationResult(BaseModel):
    is_valid: bool
    issues: list[str] = []


def create_validate_blog_post_agent(model=None):
    """
    Create an agent to comprehensively validate blog post content.

    Returns validation result with specific issues if invalid.
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=BlogPostValidationResult,
        system_prompt="""
You are an expert content quality validator for blog posts.

Analyze the provided blog post content and determine if it meets publication quality standards.

Check for:
1. **Completeness**: Does the post have a proper ending? Is it cut off mid-sentence or mid-thought?
2. **Length**: Is there substantial content (at least 2500-3000 characters)?
3. **Placeholders**: Are there any placeholder text like [INSERT X], [TODO], [EXAMPLE], {placeholder}, etc.?
4. **Structure**: Does it start with regular text (not a header like # or ##)?
5. **Quality**: Is the content coherent and well-formed?

Return:
- is_valid: True if the content passes ALL checks, False otherwise
- issues: List of specific problems found (empty if valid)

Be thorough but fair. Minor imperfections are okay if the content is publishable.
        """,  # noqa: E501
        retries=1,
        model_settings={"temperature": 0.1},
    )

    return agent
