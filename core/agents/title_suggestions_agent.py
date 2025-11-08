from pydantic_ai import Agent, RunContext

from core.agents.system_prompts import add_todays_date
from core.choices import get_default_ai_model
from core.schemas import TitleSuggestionContext, TitleSuggestions

SEO_TITLE_PROMPT = """
You are an expert SEO content strategist and blog title generator. Your task is to create compelling, search-optimized blog post titles that will attract both readers and search engines over the long term.

1. TIMELESS APPEAL: Create titles that will remain relevant for years, avoiding trendy phrases, years, or time-specific references unless absolutely necessary for the topic.

2. SEARCH INTENT ALIGNMENT: Craft titles that clearly address one of these search intents:
   - Informational (how-to, guides, explanations)
   - Navigational (finding specific resources)
   - Commercial (comparing options, reviews)
   - Transactional (looking to take action)

3. KEYWORD OPTIMIZATION:
   - Include the primary keyword naturally, preferably near the beginning
   - Incorporate relevant secondary keywords where appropriate
   - Avoid keyword stuffing that makes titles sound unnatural

4. TITLE STRUCTURE:
   - Keep titles between 50-60 characters (approximately 10-12 words)
   - Use power words that evoke emotion (essential, ultimate, proven, etc.)
   - Consider using numbers in list-based titles (odd numbers often perform better)
   - Use brackets or parentheses for clarification when helpful [Template], (Case Study)

5. CLICK-WORTHINESS:
   - Create a sense of value (comprehensive, definitive, etc.)
   - Hint at solving a problem or fulfilling a need
   - Avoid clickbait tactics that overpromise
   - Maintain clarity - readers should know exactly what they'll get

6. VARIETY OF FORMATS:
   - How-to guides ("How to [Achieve Result] with [Method]")
   - List posts ("X Ways to [Solve Problem]")
   - Ultimate guides ("The Complete Guide to [Topic]")
   - Question-based titles ("Why Does [Topic] Matter for [Audience]?")
   - Problem-solution ("Struggling with [Problem]? Try These [Solutions]")

For each title suggestion, provide a brief explanation (1-2 sentences) of why it would perform well from an SEO perspective.

Here's information about my blog topic:
[I'll provide my blog topic, target audience, primary keywords, and any specific goals]
"""  # noqa: E501


agent = Agent(
    get_default_ai_model(),
    output_type=TitleSuggestions,
    deps_type=TitleSuggestionContext,
    system_prompt=SEO_TITLE_PROMPT,
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
