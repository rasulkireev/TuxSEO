from django.utils import timezone
from pydantic_ai import Agent

from core.agents.schemas import (
    BlogPostSectionContentGenerationContext,
    GeneratedBlogPostSectionContentSchema,
)
from core.choices import ContentType, get_default_ai_model
from core.prompts import GENERATE_CONTENT_SYSTEM_PROMPTS

SECTION_CONTENT_SYSTEM_PROMPT = """
You are an expert blog post writer.

Your task: write the content for ONE blog post section (the body of the section only).

Rules:
- Do NOT write the Introduction or Conclusion.
- Do NOT include the section title as a markdown header. No leading '#', '##', or '###'.
- Avoid markdown headings entirely. Use paragraphs, bullet lists, and numbered lists only when useful.
- Use the provided "Previous sections" to maintain continuity and avoid repetition.
- Use the provided research link outputs as factual grounding. Do not invent sources or cite URLs.
- Keep the section coherent with the overall outline and the order position provided.
- Do not add placeholders.
"""


def create_generate_blog_post_section_content_agent(
    content_type: ContentType = ContentType.SHARING, model=None
):
    """
    Create an agent to generate the content for a single middle section of a blog post.
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=GeneratedBlogPostSectionContentSchema,
        deps_type=BlogPostSectionContentGenerationContext,
        system_prompt=(
            SECTION_CONTENT_SYSTEM_PROMPT
            + "\n\n"
            + (GENERATE_CONTENT_SYSTEM_PROMPTS.get(content_type, "") or "")
        ),
        retries=2,
        model_settings={"max_tokens": 16000, "temperature": 0.7},
    )

    @agent.system_prompt
    def add_section_content_context(ctx) -> str:
        section_context: BlogPostSectionContentGenerationContext = ctx.deps
        generation_context = section_context.blog_post_generation_context
        project_details = generation_context.project_details
        title_suggestion = generation_context.title_suggestion
        target_keywords = title_suggestion.target_keywords or []

        other_titles = [title for title in (section_context.other_section_titles or []) if title]
        other_titles_text = "\n".join([f"- {title}" for title in other_titles]) or "- (none)"

        previous_sections = section_context.previous_sections or []
        previous_sections_text = ""
        for previous_section_index, previous_section in enumerate(previous_sections, start=1):
            previous_sections_text += (
                f"\nPrevious section {previous_section_index}: {previous_section.title}\n"
                f"{previous_section.content}\n"
            )
        if not previous_sections_text.strip():
            previous_sections_text = "\n(none)\n"

        research_questions_text = ""
        for question_index, question in enumerate(
            section_context.research_questions or [], start=1
        ):
            research_questions_text += (
                f"\nResearch question {question_index}: {question.question}\n"
            )
            for link_index, link in enumerate(question.research_links or [], start=1):
                research_questions_text += (
                    f"\nAnswered research link {link_index}:\n"
                    f"- summary_for_question_research:\n{link.summary_for_question_research}\n"
                    f"- general_summary:\n{link.general_summary}\n"
                    f"- answer_to_question:\n{link.answer_to_question}\n"
                )

        if not research_questions_text.strip():
            research_questions_text = "\n(none)\n"

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

Outline coherence:
- Other section titles:
{other_titles_text}

Current section to write:
- Section title: {section_context.section_title}
- Section order in outline: {section_context.section_order} / {section_context.total_sections}
- Section order among middle sections: {section_context.research_section_order} / {section_context.total_research_sections}

Previous sections (for continuity; do not repeat content):
{previous_sections_text}

Research answers for this section (only include content that is supported by these answers):
{research_questions_text}

Language: Write in {project_details.language}.
"""

    return agent
