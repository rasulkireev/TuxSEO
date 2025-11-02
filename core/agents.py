from django.conf import settings
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from core.agent_system_prompts import (
    add_language_specification,
    add_project_details,
    add_project_pages,
    add_target_keywords,
    add_title_details,
    add_webpage_content,
)
from core.choices import AIModel, get_default_ai_model
from core.schemas import (
    BlogPostGenerationContext,
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
    OpenAIModel(
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


@competitor_vs_title_agent.system_prompt
def add_competitor_vs_context(ctx):
    from pydantic_ai import RunContext
    
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
