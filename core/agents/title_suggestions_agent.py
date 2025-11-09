from pydantic_ai import Agent, RunContext

from core.agents.schemas import TitleSuggestionContext, TitleSuggestions
from core.agents.system_prompts import add_todays_date
from core.choices import ContentType, get_default_ai_model
from core.prompts import TITLE_SUGGESTION_SYSTEM_PROMPTS


def create_title_suggestions_agent(content_type=ContentType.SHARING, model=None):  # noqa: C901
    """Create and configure a title suggestions agent for a specific content type."""
    agent = Agent(
        model or get_default_ai_model(),
        output_type=TitleSuggestions,
        deps_type=TitleSuggestionContext,
        system_prompt=TITLE_SUGGESTION_SYSTEM_PROMPTS[content_type],
        retries=2,
        model_settings={"temperature": 0.9},
    )

    agent.system_prompt(add_todays_date)

    @agent.system_prompt
    def add_project_details(ctx: RunContext[TitleSuggestionContext]) -> str:
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
    def add_number_of_titles_to_generate(ctx: RunContext[TitleSuggestionContext]) -> str:
        return f"""IMPORTANT: Generate only {ctx.deps.num_titles} titles."""

    @agent.system_prompt
    def add_language_specification(ctx: RunContext[TitleSuggestionContext]) -> str:
        project = ctx.deps.project_details
        return f"""
            IMPORTANT: Generate all titles in {project.language} language.
            Make sure the titles are grammatically correct and culturally
            appropriate for {project.language}-speaking audiences.
        """

    @agent.system_prompt
    def add_user_prompt(ctx: RunContext[TitleSuggestionContext]) -> str:
        if not ctx.deps.user_prompt:
            return ""

        return f"""
            IMPORTANT USER REQUEST: The user has specifically requested the following:
            "{ctx.deps.user_prompt}"

            This is a high-priority requirement. Make sure to incorporate this guidance
            when generating titles while still maintaining SEO best practices and readability.
        """

    @agent.system_prompt
    def add_feedback_history(ctx: RunContext[TitleSuggestionContext]) -> str:
        feedback_sections = []

        if ctx.deps.neutral_suggestions:
            neutral = "\n".join(f"- {title}" for title in ctx.deps.neutral_suggestions)
            feedback_sections.append(
                f"""
                Title Suggestions that users have not yet liked or disliked:
                {neutral}
            """
            )

        if ctx.deps.liked_suggestions:
            liked = "\n".join(f"- {title}" for title in ctx.deps.liked_suggestions)
            feedback_sections.append(
                f"""
                Liked Title Suggestions:
                {liked}
            """
            )

        if ctx.deps.disliked_suggestions:
            disliked = "\n".join(f"- {title}" for title in ctx.deps.disliked_suggestions)
            feedback_sections.append(
                f"""
                Disliked Title Suggestions:
                {disliked}
            """
            )

        if feedback_sections:
            feedback_sections.append(
                """
                Use this feedback to guide your title generation.
                Create titles that are thematically similar to the "Liked" titles,
                and avoid any stylistic or thematic patterns from the "Disliked" titles.

                IMPORTANT!
                You must generate completely new and unique titles.
                Do not repeat or create minor variations of any titles listed above in the
                "Previously Generated", "Liked", or "Disliked" sections.
                Your primary goal is originality.
                """
            )

        return "\n".join(feedback_sections)

    return agent
