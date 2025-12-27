from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from django_q.tasks import async_task
from exa_py import Exa

from core.agents.blog_post_outline_agent import (
    create_blog_post_outline_agent,
    create_blog_post_section_research_questions_agent,
)
from core.agents.research_link_summary_agent import (
    create_contextual_research_link_summary_agent,
    create_general_research_link_summary_agent,
)
from core.agents.schemas import (
    BlogPostGenerationContext,
    ResearchLinkContextualSummaryContext,
    WebPageContent,
)
from core.choices import ContentType
from core.content_generator.utils import get_exa_date_range_iso_strings
from core.models import (
    GeneratedBlogPost,
    GeneratedBlogPostResearchLink,
    GeneratedBlogPostResearchQuestion,
    GeneratedBlogPostSection,
)
from core.utils import get_markdown_content, run_agent_synchronously
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


INTRODUCTION_SECTION_TITLE = "Introduction"
CONCLUSION_SECTION_TITLE = "Conclusion"
NON_RESEARCH_SECTION_TITLES = {INTRODUCTION_SECTION_TITLE, CONCLUSION_SECTION_TITLE}
MAX_RESEARCH_LINK_MARKDOWN_CHARS_FOR_SUMMARY = 25_000


def _create_blog_post_generation_context(
    *, title_suggestion, content_type_to_use: str
) -> BlogPostGenerationContext:
    keywords_to_use = title_suggestion.get_blog_post_keywords()
    return BlogPostGenerationContext(
        project_details=title_suggestion.project.project_details,
        title_suggestion=title_suggestion.title_suggestion_schema,
        project_keywords=keywords_to_use,
        project_pages=[],
        content_type=content_type_to_use,
    )


def generate_sections_to_create(*, title_suggestion, content_type: str | None = None) -> list[str]:
    """
    Step 1: Generate the section titles we will create (one AI query).
    """
    if title_suggestion is None:
        raise ValueError("title_suggestion is required")

    if not title_suggestion.project_id:
        raise ValueError("title_suggestion must be associated to a project")

    content_type_to_use = content_type or title_suggestion.content_type or ContentType.SHARING
    outline_context = _create_blog_post_generation_context(
        title_suggestion=title_suggestion,
        content_type_to_use=content_type_to_use,
    )

    outline_agent = create_blog_post_outline_agent()
    outline_result = run_agent_synchronously(
        outline_agent,
        "Generate the blog post outline sections.",
        deps=outline_context,
        function_name="generate_sections_to_create",
        model_name="GeneratedBlogPost",
    )

    outline_sections = (
        outline_result.output.sections if outline_result and outline_result.output else []
    )

    middle_section_titles = [
        (section.title or "").strip()
        for section in outline_sections
        if (section.title or "").strip()
    ]

    return [INTRODUCTION_SECTION_TITLE, *middle_section_titles, CONCLUSION_SECTION_TITLE]


def create_blog_post_and_sections(
    *, title_suggestion, section_titles: list[str], content_type: str | None = None
):
    """
    Step 1b: Persist the GeneratedBlogPost + GeneratedBlogPostSection rows.
    """
    content_type_to_use = content_type or title_suggestion.content_type or ContentType.SHARING
    tags = ", ".join(title_suggestion.target_keywords) if title_suggestion.target_keywords else ""

    with transaction.atomic():
        blog_post = GeneratedBlogPost.objects.create(
            project=title_suggestion.project,
            title_suggestion=title_suggestion,
            title=title_suggestion.title,
            description=title_suggestion.suggested_meta_description,
            slug=slugify(title_suggestion.title),
            tags=tags,
            content="",
        )

        for section_order, section_title in enumerate(section_titles):
            GeneratedBlogPostSection.objects.create(
                blog_post=blog_post,
                title=(section_title or "")[:250],
                content="",
                order=section_order,
            )

    logger.info(
        "[ContentGenerator] Blog post initialized",
        blog_post_id=blog_post.id,
        title_suggestion_id=title_suggestion.id,
        project_id=title_suggestion.project_id,
        num_sections_created=len(section_titles),
        content_type=content_type_to_use,
    )

    return blog_post


def queue_research_question_generation_for_sections(*, blog_post_id: int) -> int:
    """
    Step 2: Queue one task per (research) section to generate questions.
    """
    blog_post = (
        GeneratedBlogPost.objects.prefetch_related("blog_post_sections")
        .filter(id=blog_post_id)
        .first()
    )
    if not blog_post:
        raise ValueError(f"GeneratedBlogPost not found: {blog_post_id}")

    blog_post_sections = list(blog_post.blog_post_sections.all())
    research_sections = [
        section
        for section in blog_post_sections
        if (section.title or "").strip() not in NON_RESEARCH_SECTION_TITLES
    ]

    for section in research_sections:
        async_task(
            "core.content_generator.tasks.generate_research_questions_for_section_task",
            section.id,
            group="Generate Research Questions",
        )

    logger.info(
        "[ContentGenerator] Queued research question generation tasks",
        blog_post_id=blog_post.id,
        num_sections=len(blog_post_sections),
        num_research_sections=len(research_sections),
    )

    return len(research_sections)


def init_blog_post_content_generation(title_suggestion, content_type: str | None = None):
    """
    Pipeline entrypoint (currently stops after queuing tasks).

    Step 1: generate sections we will create
    Step 2: queue tasks to generate questions for each section
    Step 3: (handled by the tasks) queue tasks to fetch Exa links for each generated question
    Step 4: next steps later
    """
    section_titles = generate_sections_to_create(
        title_suggestion=title_suggestion, content_type=content_type
    )
    blog_post = create_blog_post_and_sections(
        title_suggestion=title_suggestion,
        section_titles=section_titles,
        content_type=content_type,
    )
    queue_research_question_generation_for_sections(blog_post_id=blog_post.id)
    return blog_post


def populate_research_links_for_question_from_exa(
    research_question_id: int,
    num_results_per_question: int = 2,
    months_back: int = 6,
):
    """
    Step 3: Get links for one question from Exa (called via a task per question).
    """
    research_question = (
        GeneratedBlogPostResearchQuestion.objects.select_related("blog_post")
        .filter(id=research_question_id)
        .first()
    )
    if not research_question:
        raise ValueError(f"GeneratedBlogPostResearchQuestion not found: {research_question_id}")

    blog_post = research_question.blog_post
    if not blog_post:
        raise ValueError(f"GeneratedBlogPost missing on research question: {research_question_id}")

    research_question_text = (research_question.question or "").strip()
    if not research_question_text:
        return 0

    start_date_iso_format, end_date_iso_format = get_exa_date_range_iso_strings(
        months_back=months_back
    )
    exa = Exa(api_key=settings.EXA_API_KEY)

    exa_response = exa.search(
        research_question_text,
        end_crawl_date=end_date_iso_format,
        end_published_date=end_date_iso_format,
        start_crawl_date=start_date_iso_format,
        start_published_date=start_date_iso_format,
        num_results=num_results_per_question,
        type="auto",
    )

    exa_results = (
        exa_response.results
        if hasattr(exa_response, "results")
        else (exa_response or {}).get("results", [])
    )
    exa_results = exa_results or []

    num_links_upserted = 0
    num_scrape_tasks_queued = 0

    for result in exa_results:
        if hasattr(result, "url"):
            url = getattr(result, "url", "") or ""
            title = getattr(result, "title", "") or ""
            author = getattr(result, "author", "") or ""
            published_date_raw = getattr(result, "publishedDate", None)
        else:
            url = (result or {}).get("url", "") or ""
            title = (result or {}).get("title", "") or ""
            author = (result or {}).get("author", "") or ""
            published_date_raw = (result or {}).get("publishedDate") or (result or {}).get(
                "published_date"
            )

        url = url.strip()
        if not url.startswith(("http://", "https://")):
            continue

        if len(url) > 200:
            continue

        published_date = parse_datetime(published_date_raw) if published_date_raw else None
        if published_date and timezone.is_naive(published_date):
            published_date = timezone.make_aware(
                published_date, timezone=timezone.get_current_timezone()
            )

        research_link, _created = GeneratedBlogPostResearchLink.objects.update_or_create(
            blog_post=blog_post,
            research_question=research_question,
            url=url,
            defaults={
                "title": title[:500],
                "author": author[:250],
                "published_date": published_date,
            },
        )

        num_links_upserted += 1

        should_queue_scrape_task = not (research_link.content or "").strip()
        if should_queue_scrape_task:
            async_task(
                "core.content_generator.tasks.scrape_research_link_content_task",
                research_link.id,
                group="Scrape Research Links",
            )
            num_scrape_tasks_queued += 1

    logger.info(
        "[ContentGenerator] Exa research link search completed (single question)",
        blog_post_id=blog_post.id,
        research_question_id=research_question.id,
        num_links_upserted=num_links_upserted,
        num_scrape_tasks_queued=num_scrape_tasks_queued,
        num_results_per_question=num_results_per_question,
        months_back=months_back,
    )

    return num_links_upserted


def scrape_research_link_content(*, research_link_id: int) -> bool:
    """
    Step 4a: For a single research link, fetch the page content using Jina Reader and store it.

    Returns: True if content is present after the operation, False otherwise.
    """
    research_link = (
        GeneratedBlogPostResearchLink.objects.select_related(
            "blog_post",
            "blog_post__title_suggestion",
            "blog_post__project",
            "research_question",
            "research_question__section",
        )
        .filter(id=research_link_id)
        .first()
    )
    if not research_link:
        raise ValueError(f"GeneratedBlogPostResearchLink not found: {research_link_id}")

    url = (research_link.url or "").strip()
    if not url.startswith(("http://", "https://")):
        logger.info(
            "[ContentGenerator] Skipping scrape/summarize for invalid research link url",
            research_link_id=research_link.id,
            url=url,
        )
        return 0

    blog_post = research_link.blog_post
    research_question = research_link.research_question
    if not blog_post or not research_question:
        raise ValueError(f"Research link missing blog_post/research_question: {research_link_id}")

    should_fetch_page_content = not (research_link.content or "").strip()
    if not should_fetch_page_content:
        logger.info(
            "[ContentGenerator] Research link already scraped; skipping",
            research_link_id=research_link.id,
            blog_post_id=blog_post.id,
        )
        return True

    page_title = research_link.title
    page_description = research_link.description
    page_markdown_content = research_link.content

    scraped_title, scraped_description, scraped_content = get_markdown_content(url)
    if not scraped_content.strip():
        logger.warning(
            "[ContentGenerator] Jina Reader returned empty content for research link",
            research_link_id=research_link.id,
            blog_post_id=blog_post.id,
            url=url,
        )
        return False

    page_title = scraped_title or page_title
    page_description = scraped_description or ""
    page_markdown_content = scraped_content

    if not (page_markdown_content or "").strip():
        logger.warning(
            "[ContentGenerator] Research link has empty content; cannot summarize",
            research_link_id=research_link.id,
            blog_post_id=blog_post.id,
            url=url,
        )
        return False

    update_fields: list[str] = []

    research_link.date_scraped = timezone.now()
    update_fields.append("date_scraped")

    research_link.title = (page_title or "")[:500]
    update_fields.append("title")

    research_link.description = page_description or ""
    update_fields.append("description")

    research_link.content = page_markdown_content or ""
    update_fields.append("content")

    research_link.save(update_fields=list(dict.fromkeys(update_fields)))

    logger.info(
        "[ContentGenerator] Research link scraped",
        research_link_id=research_link.id,
        blog_post_id=blog_post.id,
        research_question_id=research_question.id,
        updated_fields=update_fields,
        url=url,
    )

    return True


def analyze_research_link_content(*, research_link_id: int) -> int:
    """
    Step 4b: For a single research link (that already has content), generate:
    - a general page summary
    - a blog-post-contextual summary for the research question/section

    Returns: number of fields updated on the research link.
    """
    research_link = (
        GeneratedBlogPostResearchLink.objects.select_related(
            "blog_post",
            "blog_post__title_suggestion",
            "blog_post__project",
            "research_question",
            "research_question__section",
        )
        .filter(id=research_link_id)
        .first()
    )
    if not research_link:
        raise ValueError(f"GeneratedBlogPostResearchLink not found: {research_link_id}")

    blog_post = research_link.blog_post
    research_question = research_link.research_question
    if not blog_post or not research_question:
        raise ValueError(f"Research link missing blog_post/research_question: {research_link_id}")

    url = (research_link.url or "").strip()
    page_markdown_content = (research_link.content or "").strip()
    if not page_markdown_content:
        logger.info(
            "[ContentGenerator] Research link has no content yet; skipping analysis",
            research_link_id=research_link.id,
            blog_post_id=blog_post.id,
            url=url,
        )
        return 0

    should_run_general_summary = not (research_link.general_summary or "").strip()
    should_run_contextual_summary = not (research_link.summary_for_question_research or "").strip()
    if not should_run_general_summary and not should_run_contextual_summary:
        logger.info(
            "[ContentGenerator] Research link already analyzed; skipping",
            research_link_id=research_link.id,
            blog_post_id=blog_post.id,
        )
        return 0

    webpage_content = WebPageContent(
        title=(research_link.title or "").strip(),
        description=(research_link.description or "").strip(),
        markdown_content=page_markdown_content[:MAX_RESEARCH_LINK_MARKDOWN_CHARS_FOR_SUMMARY],
    )

    update_fields: list[str] = []

    if should_run_general_summary:
        general_summary_agent = create_general_research_link_summary_agent()
        general_summary_result = run_agent_synchronously(
            general_summary_agent,
            "Summarize this page.",
            deps=webpage_content,
            function_name="analyze_research_link_content.general_summary",
            model_name="GeneratedBlogPostResearchLink",
        )
        research_link.general_summary = (general_summary_result.output.summary or "").strip()
        update_fields.append("general_summary")

    if should_run_contextual_summary:
        title_suggestion = blog_post.title_suggestion
        if not title_suggestion:
            raise ValueError(f"GeneratedBlogPost missing title_suggestion: {blog_post.id}")

        content_type_to_use = title_suggestion.content_type or ContentType.SHARING
        blog_post_generation_context = _create_blog_post_generation_context(
            title_suggestion=title_suggestion,
            content_type_to_use=content_type_to_use,
        )

        section_title = (getattr(research_question.section, "title", "") or "").strip()
        research_question_text = (research_question.question or "").strip()

        contextual_summary_agent = create_contextual_research_link_summary_agent()
        contextual_summary_deps = ResearchLinkContextualSummaryContext(
            url=url,
            web_page_content=webpage_content,
            blog_post_generation_context=blog_post_generation_context,
            blog_post_title=(blog_post.title or title_suggestion.title or "").strip(),
            section_title=section_title,
            research_question=research_question_text,
        )
        contextual_summary_result = run_agent_synchronously(
            contextual_summary_agent,
            "Summarize this page specifically to help answer the research question for the blog post section.",  # noqa: E501
            deps=contextual_summary_deps,
            function_name="analyze_research_link_content.contextual_summary",
            model_name="GeneratedBlogPostResearchLink",
        )
        research_link.summary_for_question_research = (
            contextual_summary_result.output.summary or ""
        ).strip()
        update_fields.append("summary_for_question_research")

    research_link.date_analyzed = timezone.now()
    update_fields.append("date_analyzed")

    research_link.save(update_fields=list(dict.fromkeys(update_fields)))

    logger.info(
        "[ContentGenerator] Research link analyzed",
        research_link_id=research_link.id,
        blog_post_id=blog_post.id,
        research_question_id=research_question.id,
        updated_fields=update_fields,
        url=url,
    )

    return len(set(update_fields))


def generate_research_questions_for_section(*, section_id: int) -> list[int]:
    """
    Step 2 (task): Generate research questions for a single section.

    Returns: list of created GeneratedBlogPostResearchQuestion IDs.
    """
    section = (
        GeneratedBlogPostSection.objects.select_related(
            "blog_post",
            "blog_post__title_suggestion",
            "blog_post__project",
        )
        .filter(id=section_id)
        .first()
    )
    if not section:
        raise ValueError(f"GeneratedBlogPostSection not found: {section_id}")

    section_title = (section.title or "").strip()
    if section_title in NON_RESEARCH_SECTION_TITLES:
        logger.info(
            "[ContentGenerator] Skipping research question generation for non-research section",
            section_id=section.id,
            section_title=section_title,
            blog_post_id=section.blog_post_id,
        )
        return []

    blog_post = section.blog_post
    if not blog_post or not blog_post.title_suggestion_id:
        raise ValueError(f"Section is missing blog_post/title_suggestion: {section_id}")

    title_suggestion = blog_post.title_suggestion
    content_type_to_use = title_suggestion.content_type or ContentType.SHARING
    outline_context = _create_blog_post_generation_context(
        title_suggestion=title_suggestion,
        content_type_to_use=content_type_to_use,
    )

    research_questions_agent = create_blog_post_section_research_questions_agent()
    questions_result = run_agent_synchronously(
        research_questions_agent,
        f"Generate research questions for section: {section_title}",
        deps=outline_context,
        function_name="generate_research_questions_for_section",
        model_name="GeneratedBlogPost",
    )

    questions = (
        questions_result.output.questions if questions_result and questions_result.output else []
    )

    questions_to_create = []
    for question in questions:
        research_question_text = (question or "").strip()
        if not research_question_text:
            continue
        questions_to_create.append(
            GeneratedBlogPostResearchQuestion(
                blog_post=blog_post,
                section=section,
                question=research_question_text[:250],
            )
        )

    created_questions = GeneratedBlogPostResearchQuestion.objects.bulk_create(questions_to_create)
    created_question_ids = [
        created_question.id for created_question in created_questions if created_question.id
    ]

    logger.info(
        "[ContentGenerator] Research questions generated",
        section_id=section.id,
        blog_post_id=blog_post.id,
        num_questions_created=len(created_question_ids),
    )

    return created_question_ids
