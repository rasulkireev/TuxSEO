from django.conf import settings
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from core.agents.models import AIModel
from core.agents.schemas import CompetitorVsPostContext
from core.agents.system_prompts import add_project_pages, markdown_lists


def create_competitor_vs_blog_post_agent(model=None):
    """
    Create an agent to generate comparison blog posts between products using web search.

    Args:
        model: Optional AI model to use. Defaults to Perplexity Sonar for web search capabilities.

    Returns:
        Configured Agent instance
    """
    if model is None:
        model = OpenAIChatModel(
            AIModel.PERPLEXITY_SONAR,
            provider=OpenAIProvider(
                base_url="https://api.perplexity.ai",
                api_key=settings.PERPLEXITY_API_KEY,
            ),
        )

    agent = Agent(
        model,
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

    agent.system_prompt(markdown_lists)
    agent.system_prompt(add_project_pages)

    @agent.system_prompt
    def output_format() -> str:
        return """
            Return only the text. Don't surround the text with ```markdown or ```.
        """

    @agent.system_prompt
    def links_insertion() -> str:
        return """
            Instead of leaving reference to links in the text (like this 'sample text[1]'), insert the links into the text in markdown format.
            For example, if the text is 'sample text[1]', the link should be inserted like this: '[sample text](https://www.example.com)'.
        """  # noqa: E501

    @agent.system_prompt
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

    return agent
