from pydantic import BaseModel
from pydantic_ai import Agent

from core.agents.models import get_default_ai_model


class BlogPostValidationResult(BaseModel):
    is_valid: bool
    issues: list[str] = []


def create_validate_blog_post_agent(model=None):
    agent = Agent(
        model or get_default_ai_model(),
        output_type=BlogPostValidationResult,
        system_prompt="""
You are an expert content quality validator for blog posts.

Analyze the provided blog post content and determine if it meets publication quality standards.

Be thorough but fair. Minor imperfections are okay if the content is publishable.
        """,  # noqa: E501
        retries=1,
        model_settings={"temperature": 0.1, "thinking_budget": 0},
    )

    @agent.system_prompt
    def validations_to_check() -> str:
        return """
        Validations to check:
        1. **Completeness**:
          Does the post have a proper ending? Is it cut off mid-sentence or mid-thought?
        2. **Length**:
          Is there substantial content (at least 2500-3000 characters)?
        3. **Placeholders**:
          Are there any placeholder text like [INSERT X], [TODO], [EXAMPLE], {placeholder}, etc.?
        4. **Structure**:
          Does it start with regular text (not a header like # or ##)?
        """

    return agent
