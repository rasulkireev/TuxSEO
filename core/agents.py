from pydantic_ai import Agent, RunContext

from core.schemas import (
    BlogPostGenerationContext,
    GeneratedBlogPostSchema,
    ProjectDetails,
    ProjectPageDetails,
    TitleSuggestion,
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


@content_editor_agent.system_prompt
def add_project_details(ctx: RunContext[BlogPostGenerationContext]) -> str:
    project = ctx.deps.project_details
    return f"""
        Project Details:
        - Project Name: {project.name}
        - Project Type: {project.type}
        - Project Summary: {project.summary}
        - Blog Theme: {project.blog_theme}
        - Founders: {project.founders}
        - Key Features: {project.key_features}
        - Target Audience: {project.target_audience_summary}
        - Pain Points: {project.pain_points}
        - Product Usage: {project.product_usage}
    """


@content_editor_agent.system_prompt
def add_project_pages(ctx: RunContext[BlogPostGenerationContext]) -> str:
    pages = ctx.deps.project_pages
    if pages:
        instruction = """
          Below is the list of pages this project has. You can reference them in
          the content you are editing where it makes sense.\n
        """
        for page in pages:
            instruction += f"""
              --------
              - Title: {page.title}
              - URL: {page.url}
              - Description: {page.description}
              - Summary: {page.summary}
              --------
            """
        return instruction
    else:
        return ""


@content_editor_agent.system_prompt
def add_title_details(ctx: RunContext[BlogPostGenerationContext]) -> str:
    title = ctx.deps.title_suggestion
    return f"""
        Title Suggestion:
        - Title: {title.title}
        - Description: {title.description}
        - Category: {title.category}
        - Target Keywords: {
        ", ".join(title.target_keywords) if title.target_keywords else "None specified"
    }
        - Suggested Meta Description: {
        title.suggested_meta_description
        if title.suggested_meta_description
        else "None specified"
    }
    """


@content_editor_agent.system_prompt
def add_language_specification(ctx: RunContext[BlogPostGenerationContext]) -> str:
    return f"""
        IMPORTANT: Generate the content in {ctx.deps.project_details.language} language.
        Make sure the content is grammatically correct and culturally appropriate for
        {ctx.deps.project_details.language}-speaking audiences.
    """


@content_editor_agent.system_prompt
def add_target_keywords(ctx: RunContext[BlogPostGenerationContext]) -> str:
    if ctx.deps.project_keywords:
        keywords_list = ", ".join(ctx.deps.project_keywords)
        return f"""
            Focus Keywords for SEO
            The user wants to focus on these specific keywords in the blog post:
            {keywords_list}

            Please incorporate these keywords naturally throughout the content where appropriate.
            Don't force them in, but use them when they fit contextually and help improve the readability and SEO value of the post.
            Don't make them bold, just a regular part of the text.
        """
    else:
        return ""


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


@summarize_page_agent.system_prompt
def add_page_content(ctx: RunContext[WebPageContent]) -> str:
    return (
        "Web page content to summarize:"
        f"Title: {ctx.deps.title}"
        f"Description: {ctx.deps.description}"
        f"Content: {ctx.deps.markdown_content}"
    )
