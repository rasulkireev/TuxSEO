from django.utils import timezone
from pydantic_ai import Agent

from core.agents.schemas import (
    BlogPostIntroConclusionGenerationContext,
    GeneratedBlogPostIntroConclusionSchema,
)
from core.choices import ContentType, get_default_ai_model
from core.prompts import GENERATE_CONTENT_SYSTEM_PROMPTS

INTRO_CONCLUSION_SYSTEM_PROMPT = """
You are an expert blog post writer.

Your task: write BOTH the Introduction and the Conclusion for a blog post in a single response.

Rules:
- Return two fields only: introduction and conclusion.
- Do NOT include markdown headings for either section. No leading '#', '##', or '###'.
- Use the existing section contents as the source of truth for what the post covers.
- The introduction should set up the promise and smoothly lead into the first middle section.
- The conclusion should summarize the key takeaways and close cleanly without adding new topics.
- Do not add placeholders.
"""


def create_generate_blog_post_intro_conclusion_agent(
    content_type: ContentType = ContentType.SHARING, model=None
):
    """
    Create an agent to generate a blog post Introduction + Conclusion in one call.
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=GeneratedBlogPostIntroConclusionSchema,
        deps_type=BlogPostIntroConclusionGenerationContext,
        system_prompt=(
            INTRO_CONCLUSION_SYSTEM_PROMPT
            + "\n\n"
            + (GENERATE_CONTENT_SYSTEM_PROMPTS.get(content_type, "") or "")
        ),
        retries=2,
        model_settings={"max_tokens": 6000, "temperature": 0.7},
    )

    @agent.system_prompt
    def add_intro_conclusion_context(ctx) -> str:
        intro_conclusion_context: BlogPostIntroConclusionGenerationContext = ctx.deps
        generation_context = intro_conclusion_context.blog_post_generation_context
        project_details = generation_context.project_details
        title_suggestion = generation_context.title_suggestion
        target_keywords = title_suggestion.target_keywords or []

        section_titles_text = (
            "\n".join(
                [
                    f"- {title}"
                    for title in (intro_conclusion_context.section_titles_in_order or [])
                    if title
                ]
            )
            or "- (none)"
        )

        sections_text = ""
        for index, section in enumerate(intro_conclusion_context.sections_in_order or [], start=1):
            sections_text += f"\nSection {index}: {section.title}\n{section.content}\n"

        if not sections_text.strip():
            sections_text = "\n(none)\n"

        return f"""
Today's date: {timezone.now().strftime("%Y-%m-%d")}

Project details:
- Project name: {project_details.name}
- Project type: {project_details.type}
- Project summary: {project_details.summary}
- Blog theme: {project_details.blog_theme}
- Key features: {project_details.key_features}
- Target audience: {project_details.target_audience_summary}
- Pain points: {project_details.pain_points}
- Product usage: {project_details.product_usage}

Blog post title suggestion:
- Title: {title_suggestion.title}
- Category: {title_suggestion.category}
- Description: {title_suggestion.description}
- Suggested meta description: {title_suggestion.suggested_meta_description}
- Target keywords: {", ".join(target_keywords) if target_keywords else "None"}

Outline:
{section_titles_text}

All existing section contents (use this as the truth of what the post covers):
{sections_text}

Language: Write in {project_details.language}.
"""

    return agent
