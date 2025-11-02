from pydantic_ai import Agent

from core.agent_system_prompts import (
    add_language_specification,
    add_project_details,
    add_project_pages,
    add_target_keywords,
    add_title_details,
    add_webpage_content,
)
from core.schemas import (
    BlogPostGenerationContext,
    ProjectDetails,
    ProjectPageDetails,
    WebPageContent,
)

########################################################

content_editor_agent = Agent(
    "google-gla:gemini-2.5-flash",
    output_type=str,
    deps_type=BlogPostGenerationContext,
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


content_editor_agent.system_prompt(add_project_details)
content_editor_agent.system_prompt(add_project_pages)
content_editor_agent.system_prompt(add_title_details)
content_editor_agent.system_prompt(add_language_specification)
content_editor_agent.system_prompt(add_target_keywords)


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
analyze_project_agent.system_prompt(add_webpage_content)


########################################################

summarize_page_agent = Agent(
    "google-gla:gemini-2.5-flash",
    output_type=ProjectPageDetails,
    deps_type=WebPageContent,
    system_prompt=(
        "You are an expert content summarizer. Based on the web page content provided, "
        "create a concise 2-3 sentence summary that captures the main purpose and key "
        "information of the page. Focus on what the page is about and its main value proposition."
    ),
    retries=2,
    model_settings={"temperature": 0.5},
)
summarize_page_agent.system_prompt(add_webpage_content)
