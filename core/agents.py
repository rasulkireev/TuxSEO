from django.conf import settings
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from core.agent_system_prompts import (
    add_inspirations,
    add_language_specification,
    add_project_details,
    add_project_pages,
    add_target_keywords,
    add_title_details,
    add_webpage_content,
    markdown_lists,
)
from core.choices import AIModel, get_default_ai_model
from core.schemas import (
    BlogPostGenerationContext,
    CompetitorVsPostContext,
    CompetitorVsTitleContext,
    ProjectDetails,
    ProjectPageDetails,
    TitleSuggestion,
    WebPageContent,
)

########################################################

content_editor_agent = Agent(
    get_default_ai_model(),
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
content_editor_agent.system_prompt(add_inspirations)


########################################################

analyze_project_agent = Agent(
    get_default_ai_model(),
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
    get_default_ai_model(),
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


########################################################

competitor_vs_title_agent = Agent(
    OpenAIChatModel(
        AIModel.PERPLEXITY_SONAR,
        provider=OpenAIProvider(
            base_url="https://api.perplexity.ai",
            api_key=settings.PERPLEXITY_API_KEY,
        ),
    ),
    output_type=TitleSuggestion,
    deps_type=CompetitorVsTitleContext,
    system_prompt="""
    You are an expert content strategist specializing in comparison content.

    Your task is to generate a single compelling blog post title that compares
    the user's project with a specific competitor. The title should:

    1. Follow the format: "[Project] vs. [Competitor]: [Compelling Angle]"
    2. Highlight a clear, specific angle for comparison (pricing, features, use cases, etc.)
    3. Be SEO-optimized and search-friendly
    4. Create intrigue and encourage clicks
    5. Be factual and professional (not clickbait)

    Use the latest information available through web search to understand both products
    and create an informed, relevant comparison angle.
    """,
    retries=2,
    model_settings={"temperature": 0.8},
)

competitor_vs_title_agent.system_prompt(markdown_lists)


@competitor_vs_title_agent.system_prompt
def add_competitor_vs_context(ctx):
    context: CompetitorVsTitleContext = ctx.deps
    project = context.project_details
    competitor = context.competitor_details

    return f"""
        Project Details:
        - Name: {project.name}
        - Type: {project.type}
        - Summary: {project.summary}
        - Key Features: {project.key_features}
        - Target Audience: {project.target_audience_summary}

        Competitor Details:
        - Name: {competitor.name}
        - URL: {competitor.url}
        - Description: {competitor.description}

        IMPORTANT: Use web search to research both products and generate
        an informed, specific comparison angle. The title should be based on
        real, up-to-date information about both products.

        Generate only ONE title suggestion with its metadata.
    """


competitor_vs_title_agent.system_prompt(add_language_specification)


########################################################

competitor_vs_blog_post_agent = Agent(
    OpenAIChatModel(
        AIModel.PERPLEXITY_SONAR,
        provider=OpenAIProvider(
            base_url="https://api.perplexity.ai",
            api_key=settings.PERPLEXITY_API_KEY,
        ),
    ),
    output_type=str,
    deps_type=CompetitorVsPostContext,
    system_prompt="""
    You are an expert content writer specializing in product comparisons.

    Create a comprehensive, comparison blog post between two products.
    The post should:

    1. Be well-researched using current information from the web
    2. Include an introduction explaining what both products are
    3. Compare key features, pricing, use cases, pros/cons
    4. Have a slight preference toward the user's project (be subtle)
    5. Include a conclusion helping readers make a decision
    6. Be SEO-optimized with proper headings and structure
    7. Be written in markdown format
    8. Be at least 2000 words
    9. Return ONLY the markdown content, no JSON or structured output

    Important formatting rules:
    - Use ## for main headings (not #)
    - Use ### for subheadings
    - Include bullet points for lists
    - Add a comparison table if relevant
    - Include internal links where appropriate
    """,
    retries=2,
    model_settings={"max_tokens": 8000, "temperature": 0.7},
)

competitor_vs_blog_post_agent.system_prompt(markdown_lists)
competitor_vs_blog_post_agent.system_prompt(add_project_pages)


@competitor_vs_blog_post_agent.system_prompt
def output_format() -> str:
    return """
        IMPORTANT: Return only the text. Don't surround the text with ```markdown or ```.
    """


@competitor_vs_blog_post_agent.system_prompt
def links_insertion() -> str:
    return """
        Instead of leaving reference to links in the text (like this 'sample text[1]'), insert the links into the text in markdown format.
        For example, if the text is 'sample text[1]', the link should be inserted like this: '[sample text](https://www.example.com)'.
    """  # noqa: E501


@competitor_vs_blog_post_agent.system_prompt
def add_competitor_vs_post_context(ctx) -> str:
    context: CompetitorVsPostContext = ctx.deps

    return f"""
        Product 1 (Our Product): {context.project_name}
        URL: {context.project_url}
        Description: {context.project_summary}

        Product 2 (Competitor): {context.competitor_name}
        URL: {context.competitor_url}
        Description: {context.competitor_description}

        Blog Post Title: "{context.title}"

        Language: {context.language}

        Use web search to gather the latest information about both products.
        Research their features, pricing, user reviews, and positioning.
        Create an informative comparison that helps readers make an informed decision.

        Have a slight preference toward {context.project_name} but remain fair and unbiased.
    """
