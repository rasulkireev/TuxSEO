from pydantic_ai import Agent, RunContext

from core.choices import get_default_ai_model
from core.schemas import ContentFixContext

agent = Agent(
    get_default_ai_model(),
    output_type=str,
    deps_type=ContentFixContext,
    system_prompt="""
    You are an expert content editor specializing in fixing incomplete or problematic blog posts.

    Your task is to fix the provided blog post content based on the specific validation issues identified.

    Guidelines:
    - Address each validation issue thoroughly
    - Maintain the original style, tone, and structure of the content
    - Keep all existing good content intact
    - Only fix what is broken or incomplete
    - If content is cut off, complete it naturally
    - If sections are missing, add them appropriately
    - Ensure the final content has a proper conclusion
    - Preserve markdown formatting
    - Do not add placeholders or temporary content

    Return ONLY the fixed markdown content, without any additional commentary or explanations.
    """,  # noqa: E501
    retries=2,
    model_settings={"temperature": 0.5},
)


@agent.system_prompt
def add_content_and_issues(ctx: RunContext[ContentFixContext]) -> str:
    issues_text = "\n".join(f"- {issue}" for issue in ctx.deps.validation_issues)
    return f"""
    Original Content:
    {ctx.deps.content}

    Validation Issues to Fix:
    {issues_text}
    """
