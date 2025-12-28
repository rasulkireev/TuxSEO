from __future__ import annotations

from django.conf import settings
from django_q.tasks import async_task

from core.content_generator.pipeline import (
    analyze_research_link_content,
    generate_intro_and_conclusion_for_blog_post,
    generate_research_questions_for_section,
    populate_generated_blog_post_content,
    populate_research_links_for_question_from_exa,
    scrape_research_link_content,
    synthesize_section_contents_for_blog_post,
)
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)

LOCAL_NUM_EXA_RESULTS_PER_QUESTION = 2


def populate_research_links_for_question_from_exa_task(
    research_question_id: int,
    num_results_per_question: int = 2,
    months_back: int = 6,
):
    """
    Populate Exa research links for one research question.
    """
    num_results_per_question_to_use = (
        LOCAL_NUM_EXA_RESULTS_PER_QUESTION if settings.DEBUG else num_results_per_question
    )
    num_links = populate_research_links_for_question_from_exa(
        research_question_id=research_question_id,
        num_results_per_question=num_results_per_question_to_use,
        months_back=months_back,
    )
    logger.info(
        "[ContentGenerator Tasks] Populated Exa research links for question",
        research_question_id=research_question_id,
        num_links_upserted=num_links,
        num_results_per_question=num_results_per_question_to_use,
        months_back=months_back,
    )
    return f"Populated {num_links} research links for research question {research_question_id}"


def scrape_research_link_content_task(research_link_id: int):
    """
    Fetch research link content using Jina Reader.
    Always queue the analysis task after the scrape attempt.

    Rationale:
    - Jina can return empty content for some URLs (parsing failures).
    - We still want the pipeline to progress and eventually synthesize sections using
      whatever research succeeded, rather than stalling forever on a few bad links.
    """
    did_fetch_content = scrape_research_link_content(research_link_id=research_link_id)
    logger.info(
        "[ContentGenerator Tasks] Scraped research link",
        research_link_id=research_link_id,
        did_fetch_content=did_fetch_content,
    )
    async_task(
        "core.content_generator.tasks.analyze_research_link_content_task",
        research_link_id,
        group="Analyze Research Links",
    )
    return f"Scraped research link {research_link_id} (did_fetch_content={did_fetch_content})"


def analyze_research_link_content_task(research_link_id: int):
    """
    Analyze a research link that has already been scraped:
    - generate general summary
    - generate blog-post contextual summary for the research question/section
    - generate an answer to the research question
    """
    num_fields_updated = analyze_research_link_content(research_link_id=research_link_id)
    logger.info(
        "[ContentGenerator Tasks] Analyzed research link",
        research_link_id=research_link_id,
        num_fields_updated=num_fields_updated,
    )
    return f"Analyzed research link {research_link_id} (updated_fields={num_fields_updated})"


def synthesize_section_contents_for_blog_post_task(blog_post_id: int):
    """
    Synthesize the content for each middle section sequentially (excluding Introduction/Conclusion).
    """
    num_sections_generated = synthesize_section_contents_for_blog_post(blog_post_id=blog_post_id)
    logger.info(
        "[ContentGenerator Tasks] Synthesized section contents for blog post",
        blog_post_id=blog_post_id,
        num_sections_generated=num_sections_generated,
    )
    return f"Synthesized {num_sections_generated} section(s) for blog post {blog_post_id}"


def generate_intro_and_conclusion_for_blog_post_task(blog_post_id: int):
    """
    Generate Introduction + Conclusion in one AI call.
    Only runs once all middle sections have content.
    """
    num_sections_updated = generate_intro_and_conclusion_for_blog_post(blog_post_id=blog_post_id)
    logger.info(
        "[ContentGenerator Tasks] Generated intro and conclusion for blog post",
        blog_post_id=blog_post_id,
        num_sections_updated=num_sections_updated,
    )
    return (
        f"Generated intro/conclusion (updated={num_sections_updated}) for blog post {blog_post_id}"
    )


def populate_generated_blog_post_content_task(blog_post_id: int):
    """
    Populate GeneratedBlogPost.content from the generated sections.
    """
    did_populate = populate_generated_blog_post_content(blog_post_id=blog_post_id)
    logger.info(
        "[ContentGenerator Tasks] Populated GeneratedBlogPost.content",
        blog_post_id=blog_post_id,
        did_populate=did_populate,
    )
    return f"Populated GeneratedBlogPost.content for blog post {blog_post_id} (did_populate={did_populate})"


def generate_research_questions_for_section_task(section_id: int):
    """
    Generate research questions for one section, then queue Exa research link tasks for each
    created question.
    """
    created_research_question_ids = generate_research_questions_for_section(section_id=section_id)

    for research_question_id in created_research_question_ids:
        async_task(
            "core.content_generator.tasks.populate_research_links_for_question_from_exa_task",
            research_question_id,
            group="Populate Research Links",
        )

    logger.info(
        "[ContentGenerator Tasks] Generated research questions for section",
        section_id=section_id,
        num_questions_created=len(created_research_question_ids),
    )
    return f"Generated {len(created_research_question_ids)} research questions for section {section_id}"  # noqa: E501
