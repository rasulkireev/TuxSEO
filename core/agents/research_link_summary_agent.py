from django.utils import timezone
from pydantic_ai import Agent, RunContext

from core.agents.schemas import (
    ResearchLinkContextualSummaryContext,
    TextSummary,
    WebPageContent,
)
from core.choices import get_default_ai_model


def _add_webpage_content_from_web_page_content(ctx: RunContext[WebPageContent]) -> str:
    return (
        "Web page content:\n"
        f"Title: {ctx.deps.title}\n"
        f"Description: {ctx.deps.description}\n"
        f"Content: {ctx.deps.markdown_content}\n"
    )


def _add_webpage_content_from_contextual_deps(
    ctx: RunContext[ResearchLinkContextualSummaryContext],
) -> str:
    web_page_content = ctx.deps.web_page_content
    return (
        "Web page content:\n"
        f"URL: {ctx.deps.url}\n"
        f"Title: {web_page_content.title}\n"
        f"Description: {web_page_content.description}\n"
        f"Content: {web_page_content.markdown_content}\n"
    )


def _add_blog_post_research_context(ctx: RunContext[ResearchLinkContextualSummaryContext]) -> str:
    blog_post_generation_context = ctx.deps.blog_post_generation_context
    project_details = blog_post_generation_context.project_details
    title_suggestion = blog_post_generation_context.title_suggestion
    target_keywords = title_suggestion.target_keywords or []

    return (
        "Context for why we are summarizing this page:\n"
        f"- Today's date: {timezone.now().strftime('%Y-%m-%d')}\n"
        f"- Project: {project_details.name}\n"
        f"- Project summary: {project_details.summary}\n"
        f"- Blog post title: {ctx.deps.blog_post_title}\n"
        f"- Blog post section: {ctx.deps.section_title}\n"
        f"- Research question: {ctx.deps.research_question}\n"
        f"- Target keywords: {', '.join(target_keywords) if target_keywords else 'None'}\n"
        "\n"
        "You must tailor the summary to help the writer answer the research question for that section.\n"  # noqa: E501
    )


def create_general_research_link_summary_agent(model=None):
    agent = Agent(
        model or get_default_ai_model(),
        output_type=TextSummary,
        deps_type=WebPageContent,
        system_prompt=(
            "You are an expert content summarizer. Summarize the web page content provided.\n"
            "Return a concise 2-3 sentence summary that captures the main purpose and key information.\n"  # noqa: E501
            "Focus on what the page is about and its main value proposition.\n"
        ),
        retries=2,
        model_settings={"temperature": 0.4},
    )
    agent.system_prompt(_add_webpage_content_from_web_page_content)
    return agent


def create_contextual_research_link_summary_agent(model=None):
    agent = Agent(
        model or get_default_ai_model(),
        output_type=TextSummary,
        deps_type=ResearchLinkContextualSummaryContext,
        system_prompt=(
            "You are a research assistant helping write a blog post.\n"
            "Summarize the page in a way that is maximally useful for answering the research question.\n"  # noqa: E501
            "Prefer concrete facts, definitions, steps, examples, and any notable stats. If the page is not relevant, say so clearly.\n"  # noqa: E501
            "Output markdown that includes:\n"
            "- A short paragraph summary\n"
            "- 'Key takeaways' as 3-7 bullet points\n"
            "- 'How this helps our section' as 1-3 bullet points\n"
        ),
        retries=2,
        model_settings={"temperature": 0.3},
    )
    agent.system_prompt(_add_blog_post_research_context)
    agent.system_prompt(_add_webpage_content_from_contextual_deps)
    return agent
