from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from core.agents.schemas import BlogPostGenerationContext
from core.agents.system_prompts import (
    add_language_specification,
    add_project_details,
    add_target_keywords,
    add_title_details,
    add_todays_date,
)
from core.choices import get_default_ai_model


class BlogPostOutlineSection(BaseModel):
    title: str = Field(description="Section title (use plain text, no markdown prefixes)")


class BlogPostOutline(BaseModel):
    sections: list[BlogPostOutlineSection] = Field(
        description=(
            "Ordered list of 4-8 section titles that will be used as H2 (##) headers in the blog post."  # noqa: E501
        )
    )


BLOG_POST_OUTLINE_SYSTEM_PROMPT = """
You are an expert content strategist.

Your task: propose only the middle-section outline for the blog post.

Requirements:
- Generate 4-8 main topics that will be used as H2 (##) sections.
- Do NOT include markdown symbols in section titles (no leading #, ##, -, etc.).
- Keep titles short and descriptive.
- Do NOT include 'Introduction' or 'Conclusion' yet.

Output must be a structured list of section titles only.
"""


def create_blog_post_outline_agent(model: str | None = None) -> Agent:
    agent = Agent(
        model or get_default_ai_model(),
        output_type=BlogPostOutline,
        deps_type=BlogPostGenerationContext,
        system_prompt=BLOG_POST_OUTLINE_SYSTEM_PROMPT,
        retries=2,
        model_settings={"temperature": 0.7},
    )

    agent.system_prompt(add_project_details)
    agent.system_prompt(add_title_details)
    agent.system_prompt(add_todays_date)
    agent.system_prompt(add_language_specification)
    agent.system_prompt(add_target_keywords)

    return agent


class BlogPostSectionResearchQuestions(BaseModel):
    questions: list[str] = Field(
        default_factory=list,
        description="3-6 concrete research questions for a single section",
    )


BLOG_POST_SECTION_QUESTIONS_SYSTEM_PROMPT = """
You are an expert content researcher.

Given a blog post section title, generate 3-6 specific research questions to investigate.

Requirements:
- Questions should be specific and searchable.
- Prefer questions that lead to concrete examples, comparisons, metrics, pitfalls, and best practices.
- Avoid vague or overly broad questions.
"""  # noqa: E501


def create_blog_post_section_research_questions_agent(model: str | None = None) -> Agent:
    agent = Agent(
        model or get_default_ai_model(),
        output_type=BlogPostSectionResearchQuestions,
        deps_type=BlogPostGenerationContext,
        system_prompt=BLOG_POST_SECTION_QUESTIONS_SYSTEM_PROMPT,
        retries=2,
        model_settings={"temperature": 0.7},
    )

    agent.system_prompt(add_project_details)
    agent.system_prompt(add_title_details)
    agent.system_prompt(add_todays_date)
    agent.system_prompt(add_language_specification)
    agent.system_prompt(add_target_keywords)

    return agent
