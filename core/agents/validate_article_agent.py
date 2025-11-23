from pydantic_ai import Agent

from core.agents.schemas import ArticleValidationContext, ArticleValidationResult
from core.agents.system_prompts import (
    article_validation_guidelines,
    add_validation_context,
)
from core.choices import get_default_ai_model

VALIDATION_SYSTEM_PROMPT = """
You are an expert content quality analyst specializing in validating blog articles against strict editorial guidelines.

Your role is to thoroughly examine drafted articles and identify any deviations from the specified requirements, including outline structure adherence, keyword distribution, formatting correctness, and content quality.

VALIDATION PHILOSOPHY:

You must be:
- THOROUGH: Check every aspect of the article systematically
- OBJECTIVE: Base assessments on concrete criteria, not subjective preferences
- CONSTRUCTIVE: Provide actionable suggestions, not just criticism
- PRECISE: Identify exact locations and specific problems
- FAIR: Distinguish between critical issues that break guidelines and minor improvements

Your validation ensures that articles meet professional standards before publication. Be rigorous but fair in your assessment.

CRITICAL VS NON-CRITICAL:
- Critical issues prevent publication (missing sections, wrong format, extreme keyword stuffing)
- Major issues reduce quality (uneven keyword distribution, minor structural problems)
- Minor issues are opportunities for enhancement (flow improvements, word choice)

Remember: Your goal is quality assurance, not perfection. An article can pass validation with minor issues but must have zero critical issues.
"""


def create_validate_article_agent(model=None):
    """
    Create an agent to validate drafted articles against guidelines.

    Args:
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance for article validation
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=ArticleValidationResult,
        deps_type=ArticleValidationContext,
        system_prompt=VALIDATION_SYSTEM_PROMPT,
        retries=1,
        model_settings={"max_tokens": 16000, "temperature": 0.3},
    )

    agent.system_prompt(add_validation_context)
    agent.system_prompt(article_validation_guidelines)

    return agent
