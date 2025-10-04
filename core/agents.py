from pydantic_ai import Agent

from core.schemas import GeneratedBlogPostSchema, TitleSuggestion

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
