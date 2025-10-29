from pydantic_ai import Agent, RunContext

from core.schemas import (
    GeneratedBlogPostSchema,
    ProjectDetails,
    TitleSuggestion,
    WebPageContent,
)

########################################################

content_editor_agent = Agent(
    "google-gla:gemini-2.5-flash",
    output_type=str,
    deps_type=[GeneratedBlogPostSchema, TitleSuggestion],
    system_prompt="""
    You are an expert content editor.

    Your task is to edit the blog post content based on the requested changes.
    """,
    retries=2,
    model_settings={"temperature": 0.3},
)


@content_editor_agent.system_prompt
def only_return_the_edited_content() -> str:
    return """
        IMPORTANT: Only return the edited content, no other text.
    """


########################################################

analyze_project_agent = Agent(
    "google-gla:gemini-2.5-flash",
    output_type=ProjectDetails,
    deps_type=WebPageContent,
    system_prompt=(
        "You are an expert content analyzer. Based on the content provided, "
        "extract and infer the requested information. Make reasonable inferences based "
        "on available content, context, and industry knowledge."
    ),
    retries=2,
)


@analyze_project_agent.system_prompt
def add_webpage_content(ctx: RunContext[WebPageContent]) -> str:
    return (
        "Web page content:"
        f"Title: {ctx.deps.title}"
        f"Description: {ctx.deps.description}"
        f"Content: {ctx.deps.markdown_content}"
    )
