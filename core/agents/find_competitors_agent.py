from django.conf import settings
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from core.choices import AIModel
from core.schemas import ProjectDetails


def create_find_competitors_agent(is_on_free_plan: bool):
    """
    Create an agent to find competitors for a project.

    Args:
        is_on_free_plan: Whether the user is on the free plan (affects number of competitors)

    Returns:
        Configured Agent instance
    """
    model = OpenAIChatModel(
        AIModel.PERPLEXITY_SONAR,
        provider=OpenAIProvider(
            base_url="https://api.perplexity.ai",
            api_key=settings.PERPLEXITY_API_KEY,
        ),
    )

    agent = Agent(
        model,
        deps_type=ProjectDetails,
        output_type=str,
        system_prompt="""
            You are a helpful assistant that helps me find competitors for my project.
        """,
        retries=2,
    )

    @agent.system_prompt
    def add_project_details(ctx: RunContext[ProjectDetails]) -> str:
        project = ctx.deps
        return f"""I'm working on a project which has the following attributes:
            Name:
            {project.name}

            Summary:
            {project.summary}

            Key Features:
            {project.key_features}

            Target Audience:
            {project.target_audience_summary}

            Pain Points Addressed:
            {project.pain_points}

            Language: {project.language}
        """

    @agent.system_prompt
    def required_data() -> str:
        return "Make sure that each competitor has a name, url, and description."

    @agent.system_prompt
    def number_of_competitors(ctx: RunContext[ProjectDetails]) -> str:
        if is_on_free_plan:
            return "Give me a list of exactly 3 competitors."
        return "Give me a list of at least 20 competitors."

    @agent.system_prompt
    def language_specification(ctx: RunContext[ProjectDetails]) -> str:
        project = ctx.deps
        return f"""
            IMPORTANT: Be mindful that competitors are likely to speak in
            {project.language} language.
        """

    @agent.system_prompt
    def location_specification(ctx: RunContext[ProjectDetails]) -> str:
        project = ctx.deps
        if project.location != "Global":
            return f"""
                IMPORTANT: Only return competitors whose target audience is in
                {project.location}.
            """
        else:
            return """
                IMPORTANT: Return competitors from all over the world.
            """

    return agent
