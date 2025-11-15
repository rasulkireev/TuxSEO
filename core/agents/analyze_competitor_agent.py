from django.utils import timezone
from pydantic_ai import Agent, RunContext

from core.agents.models import get_default_ai_model
from core.agents.schemas import CompetitorAnalysis, CompetitorAnalysisContext


def create_analyze_competitor_agent(model=None):
    """
    Create an agent to analyze a competitor against a project.

    Args:
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=CompetitorAnalysis,
        deps_type=CompetitorAnalysisContext,
        system_prompt=(
            """
            You are an expert marketer.
            Based on the competitor details and homepage content provided,
            extract and infer the requested information. Make     reasonable inferences based
            on available content, context, and industry knowledge.
            """
        ),
        retries=2,
        model_settings={"temperature": 0.8},
    )

    @agent.system_prompt
    def add_todays_date() -> str:
        return f"Today's Date: {timezone.now().strftime('%Y-%m-%d')}"

    @agent.system_prompt
    def my_project_details(ctx: RunContext[CompetitorAnalysisContext]) -> str:
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

    @agent.system_prompt
    def competitor_details(ctx: RunContext[CompetitorAnalysisContext]) -> str:
        competitor = ctx.deps.competitor_details
        return f"""
            Competitor Details:
            - Competitor Name: {competitor.name}
            - Competitor URL: {competitor.url}
            - Competitor Description: {competitor.description}
            - Competitor Homepage Content: {ctx.deps.competitor_homepage_content}
        """

    return agent
