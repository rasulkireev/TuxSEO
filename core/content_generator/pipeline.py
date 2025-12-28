from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
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
from core.agents.generate_blog_post_intro_conclusion_agent import (
    create_generate_blog_post_intro_conclusion_agent,
)
from core.agents.generate_blog_post_section_content_agent import (
    create_generate_blog_post_section_content_agent,
)
from core.agents.research_link_summary_agent import (
    create_research_link_analysis_agent,
)
from core.agents.schemas import (
    BlogPostGenerationContext,
    BlogPostIntroConclusionGenerationContext,
    BlogPostSectionContentGenerationContext,
    GeneratedBlogPostIntroConclusionSchema,
    GeneratedBlogPostSectionContentSchema,
    PriorSectionContext,
    ResearchLinkAnswerSnippet,
    ResearchLinkContextualSummaryContext,
    ResearchQuestionWithAnsweredLinks,
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
LOCAL_MAX_RESEARCH_QUESTIONS_PER_SECTION = 1
SECTION_SYNTHESIS_RETRY_CACHE_TTL_SECONDS = 6 * 60 * 60


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

    # If Exa returned no links for this question, nothing will trigger scrape/analyze kicks.
    # This "kick" is safe (it will only queue synthesis when the overall blog post is ready).
    if num_links_upserted == 0:
        maybe_queue_section_content_synthesis_for_blog_post(blog_post_id=blog_post.id)

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
    - an answer to the research question (answer_to_question)

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
        research_link.date_analyzed = timezone.now()
        research_link.save(update_fields=["date_analyzed"])
        maybe_queue_section_content_synthesis_for_blog_post(blog_post_id=blog_post.id)
        return 0

    should_run_general_summary = not (research_link.general_summary or "").strip()
    should_run_contextual_summary = not (research_link.summary_for_question_research or "").strip()
    should_run_answer_to_question = not (research_link.answer_to_question or "").strip()
    if (
        not should_run_general_summary
        and not should_run_contextual_summary
        and not should_run_answer_to_question
    ):
        logger.info(
            "[ContentGenerator] Research link already analyzed; skipping",
            research_link_id=research_link.id,
            blog_post_id=blog_post.id,
        )
        maybe_queue_section_content_synthesis_for_blog_post(blog_post_id=blog_post.id)
        return 0

    webpage_content = WebPageContent(
        title=(research_link.title or "").strip(),
        description=(research_link.description or "").strip(),
        markdown_content=page_markdown_content[:MAX_RESEARCH_LINK_MARKDOWN_CHARS_FOR_SUMMARY],
    )

    update_fields: list[str] = []

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

    analysis_agent = create_research_link_analysis_agent()
    analysis_deps = ResearchLinkContextualSummaryContext(
        url=url,
        web_page_content=webpage_content,
        blog_post_generation_context=blog_post_generation_context,
        blog_post_title=(blog_post.title or title_suggestion.title or "").strip(),
        section_title=section_title,
        research_question=research_question_text,
    )
    analysis_result = run_agent_synchronously(
        analysis_agent,
        "Analyze this page for blog-post research.",
        deps=analysis_deps,
        function_name="analyze_research_link_content.research_link_analysis",
        model_name="GeneratedBlogPostResearchLink",
    )

    if should_run_general_summary:
        research_link.general_summary = (analysis_result.output.general_summary or "").strip()
        update_fields.append("general_summary")

    if should_run_contextual_summary:
        research_link.summary_for_question_research = (
            analysis_result.output.summary_for_question_research or ""
        ).strip()
        update_fields.append("summary_for_question_research")

    if should_run_answer_to_question:
        research_link.answer_to_question = (analysis_result.output.answer_to_question or "").strip()
        update_fields.append("answer_to_question")

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

    maybe_queue_section_content_synthesis_for_blog_post(blog_post_id=blog_post.id)

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

    if settings.DEBUG:
        questions_to_create = questions_to_create[:LOCAL_MAX_RESEARCH_QUESTIONS_PER_SECTION]

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

    # If no questions were created, nothing else will trigger Exa/scrape/analysis tasks.
    # In that case, kick section synthesis so the pipeline can still proceed.
    if not created_question_ids:
        maybe_queue_section_content_synthesis_for_blog_post(blog_post_id=blog_post.id)

    return created_question_ids


def _build_research_questions_with_answered_links_for_section(
    *, section: GeneratedBlogPostSection
) -> list[ResearchQuestionWithAnsweredLinks]:
    research_questions_with_answered_links: list[ResearchQuestionWithAnsweredLinks] = []

    section_questions = list(section.research_questions.all())
    for research_question in section_questions:
        question_text = (research_question.question or "").strip()
        if not question_text:
            continue

        research_links = list(research_question.research_links.all())
        answered_links = [
            research_link
            for research_link in research_links
            if (research_link.answer_to_question or "").strip()
        ]

        research_link_snippets = []
        if answered_links:
            research_link_snippets = [
                ResearchLinkAnswerSnippet(
                    summary_for_question_research=(
                        (research_link.summary_for_question_research or "").strip()
                    ),
                    general_summary=(research_link.general_summary or "").strip(),
                    answer_to_question=(research_link.answer_to_question or "").strip(),
                )
                for research_link in answered_links
            ]

        research_questions_with_answered_links.append(
            ResearchQuestionWithAnsweredLinks(
                question=question_text,
                research_links=research_link_snippets,
            )
        )

    return research_questions_with_answered_links


def _build_prior_section_contexts(
    *, sections_in_order: list[GeneratedBlogPostSection], current_section_order: int
) -> list[PriorSectionContext]:
    prior_sections: list[PriorSectionContext] = []
    for section in sections_in_order:
        if section.order >= current_section_order:
            continue
        if (section.title or "").strip() in NON_RESEARCH_SECTION_TITLES:
            continue
        content = (section.content or "").strip()
        if not content:
            continue
        prior_sections.append(
            PriorSectionContext(title=(section.title or "").strip(), content=content)
        )
    return prior_sections


def synthesize_section_contents_for_blog_post(*, blog_post_id: int) -> int:
    """
    Step 5: Synthesize content for each middle section sequentially (excluding Introduction/Conclusion).

    Context passed to the model:
    - Project details
    - Title suggestion details
    - Current section info
    - Research link results (only for links with non-empty answer_to_question)
    - Other section titles
    - Section order + previous section content for coherence
    """
    blog_post = (
        GeneratedBlogPost.objects.select_related(
            "title_suggestion",
            "project",
        )
        .prefetch_related(
            "blog_post_sections__research_questions__research_links",
        )
        .filter(id=blog_post_id)
        .first()
    )
    if not blog_post:
        raise ValueError(f"GeneratedBlogPost not found: {blog_post_id}")

    title_suggestion = blog_post.title_suggestion
    if not title_suggestion:
        raise ValueError(f"GeneratedBlogPost missing title_suggestion: {blog_post_id}")

    content_type_to_use = title_suggestion.content_type or ContentType.SHARING
    blog_post_generation_context = _create_blog_post_generation_context(
        title_suggestion=title_suggestion,
        content_type_to_use=content_type_to_use,
    )

    sections_in_order = sorted(
        list(blog_post.blog_post_sections.all()),
        key=lambda section: (section.order, section.id),
    )

    all_section_titles = [
        (section.title or "").strip()
        for section in sections_in_order
        if (section.title or "").strip()
    ]
    total_sections = len(sections_in_order)

    middle_sections_in_order = [
        section
        for section in sections_in_order
        if (section.title or "").strip() not in NON_RESEARCH_SECTION_TITLES
    ]
    total_research_sections = len(middle_sections_in_order)

    section_agent = create_generate_blog_post_section_content_agent(
        content_type=content_type_to_use
    )

    num_sections_generated = 0
    for research_section_index, section in enumerate(middle_sections_in_order, start=1):
        section_title = (section.title or "").strip()
        if not section_title:
            continue

        existing_content = (section.content or "").strip()
        if existing_content:
            continue

        research_questions = _build_research_questions_with_answered_links_for_section(
            section=section
        )
        prior_sections = _build_prior_section_contexts(
            sections_in_order=sections_in_order,
            current_section_order=section.order,
        )

        section_context = BlogPostSectionContentGenerationContext(
            blog_post_generation_context=blog_post_generation_context,
            blog_post_title=(blog_post.title or title_suggestion.title or "").strip(),
            section_title=section_title,
            section_order=section.order,
            total_sections=total_sections,
            research_section_order=research_section_index,
            total_research_sections=total_research_sections,
            other_section_titles=all_section_titles,
            previous_sections=prior_sections,
            research_questions=research_questions,
        )

        prompt = f"Write the section body content for: {section_title}"
        generation_result = run_agent_synchronously(
            section_agent,
            prompt,
            deps=section_context,
            function_name="synthesize_section_contents_for_blog_post.section_content",
            model_name="GeneratedBlogPostSection",
        )

        generated_schema: GeneratedBlogPostSectionContentSchema | None = (
            generation_result.output if generation_result and generation_result.output else None
        )
        generated_content = (generated_schema.content if generated_schema else "").strip()
        if not generated_content:
            logger.warning(
                "[ContentGenerator] Section content generation returned empty content",
                blog_post_id=blog_post.id,
                section_id=section.id,
                section_title=section_title,
            )
            continue

        section.content = generated_content
        section.save(update_fields=["content"])
        num_sections_generated += 1

        logger.info(
            "[ContentGenerator] Section content synthesized",
            blog_post_id=blog_post.id,
            section_id=section.id,
            section_title=section_title,
            section_order=section.order,
            research_section_order=research_section_index,
            total_research_sections=total_research_sections,
            content_length=len(generated_content),
        )

    maybe_queue_intro_conclusion_generation_for_blog_post(blog_post_id=blog_post.id)
    maybe_queue_section_content_synthesis_retry_for_blog_post(blog_post_id=blog_post.id)
    return num_sections_generated


def _get_section_synthesis_retry_cache_key(*, blog_post_id: int) -> str:
    return f"content_generator:section_synthesis_retry_count:{blog_post_id}"


def maybe_queue_section_content_synthesis_retry_for_blog_post(*, blog_post_id: int) -> bool:
    """
    Retry mechanism for Step 5:

    If research is "done enough" (all links are in a terminal analyzed/attempted state),
    but some middle sections still have empty content (e.g. a model returned empty output
    or a task was missed), re-queue section synthesis a bounded number of times.
    """
    blog_post = (
        GeneratedBlogPost.objects.prefetch_related("blog_post_sections")
        .filter(id=blog_post_id)
        .first()
    )
    if not blog_post:
        return False

    sections_in_order = _get_sections_in_order_for_blog_post(blog_post)
    middle_sections = [
        section
        for section in sections_in_order
        if (section.title or "").strip() not in NON_RESEARCH_SECTION_TITLES
    ]
    has_any_middle_section_missing_content = any(
        not (section.content or "").strip() for section in middle_sections
    )
    if not has_any_middle_section_missing_content:
        return False

    # Only retry when link processing is "complete" (including failures).
    # If there are links still being processed, let the normal kicks handle it.
    links_queryset = GeneratedBlogPostResearchLink.objects.filter(blog_post_id=blog_post_id)
    has_any_pending_link = links_queryset.filter(date_analyzed__isnull=True).exists()
    if has_any_pending_link:
        return False

    max_retries = 5 if settings.DEBUG else 2
    retry_cache_key = _get_section_synthesis_retry_cache_key(blog_post_id=blog_post_id)
    retry_count = cache.get(retry_cache_key, 0) or 0
    if retry_count >= max_retries:
        logger.warning(
            "[ContentGenerator] Not retrying section synthesis; max retries reached",
            blog_post_id=blog_post_id,
            retry_count=retry_count,
            max_retries=max_retries,
            num_middle_sections=len(middle_sections),
            num_links_total=links_queryset.count(),
        )
        return False

    cache.set(retry_cache_key, retry_count + 1, timeout=SECTION_SYNTHESIS_RETRY_CACHE_TTL_SECONDS)
    async_task(
        "core.content_generator.tasks.synthesize_section_contents_for_blog_post_task",
        blog_post_id,
        group="Synthesize Section Content (Retry)",
    )
    logger.info(
        "[ContentGenerator] Queued section content synthesis retry task",
        blog_post_id=blog_post_id,
        retry_count=retry_count + 1,
        max_retries=max_retries,
        num_middle_sections=len(middle_sections),
        num_links_total=links_queryset.count(),
    )
    return True


def maybe_queue_section_content_synthesis_for_blog_post(*, blog_post_id: int) -> bool:
    """
    Queue Step 5 once research work is in a terminal state for all required inputs.

    This is intentionally best-effort + idempotent:
    - It may queue more than once, but the synthesis step skips sections that already have content.
    """
    blog_post = (
        GeneratedBlogPost.objects.prefetch_related(
            "blog_post_sections__research_questions__research_links"
        )
        .filter(id=blog_post_id)
        .first()
    )
    if not blog_post:
        return False

    sections_in_order = _get_sections_in_order_for_blog_post(blog_post)
    middle_sections_missing_content = [
        section
        for section in sections_in_order
        if (section.title or "").strip() not in NON_RESEARCH_SECTION_TITLES
        and not (section.content or "").strip()
    ]

    num_pending_links = 0
    num_scrape_tasks_queued = 0
    num_analyze_tasks_queued = 0

    for section in middle_sections_missing_content:
        section_questions = list(section.research_questions.all())
        for research_question in section_questions:
            research_links = list(research_question.research_links.all())
            for research_link in research_links:
                # Terminal state: we attempted analysis for this link (even if it failed).
                if research_link.date_analyzed is not None:
                    continue

                num_pending_links += 1

                link_content = (research_link.content or "").strip()
                if not link_content:
                    # If we haven't scraped content yet (or it failed previously but wasn't marked),
                    # re-queue a scrape attempt. The scrape task will always queue analysis next.
                    async_task(
                        "core.content_generator.tasks.scrape_research_link_content_task",
                        research_link.id,
                        group="Scrape Research Links (Retry/Kick)",
                    )
                    num_scrape_tasks_queued += 1
                    continue

                # Content exists, but analysis hasn't run yet: queue AI augmentation.
                async_task(
                    "core.content_generator.tasks.analyze_research_link_content_task",
                    research_link.id,
                    group="Analyze Research Links (Retry/Kick)",
                )
                num_analyze_tasks_queued += 1

    if num_pending_links > 0:
        logger.info(
            "[ContentGenerator] Not queuing section synthesis; research links still pending",
            blog_post_id=blog_post_id,
            num_middle_sections_missing_content=len(middle_sections_missing_content),
            num_pending_links=num_pending_links,
            num_scrape_tasks_queued=num_scrape_tasks_queued,
            num_analyze_tasks_queued=num_analyze_tasks_queued,
        )
        return False

    async_task(
        "core.content_generator.tasks.synthesize_section_contents_for_blog_post_task",
        blog_post_id,
        group="Synthesize Section Content",
    )
    logger.info(
        "[ContentGenerator] Queued section content synthesis task",
        blog_post_id=blog_post_id,
        num_middle_sections_missing_content=len(middle_sections_missing_content),
    )
    return True


def _get_sections_in_order_for_blog_post(
    blog_post: GeneratedBlogPost,
) -> list[GeneratedBlogPostSection]:
    return sorted(
        list(blog_post.blog_post_sections.all()),
        key=lambda section: (section.order, section.id),
    )


def generate_intro_and_conclusion_for_blog_post(*, blog_post_id: int) -> int:
    """
    Step 6: Generate Introduction + Conclusion in a single model call.

    Runs only when all middle sections have content.
    """
    blog_post = (
        GeneratedBlogPost.objects.select_related(
            "title_suggestion",
            "project",
        )
        .prefetch_related("blog_post_sections")
        .filter(id=blog_post_id)
        .first()
    )
    if not blog_post:
        raise ValueError(f"GeneratedBlogPost not found: {blog_post_id}")

    title_suggestion = blog_post.title_suggestion
    if not title_suggestion:
        raise ValueError(f"GeneratedBlogPost missing title_suggestion: {blog_post_id}")

    content_type_to_use = title_suggestion.content_type or ContentType.SHARING
    blog_post_generation_context = _create_blog_post_generation_context(
        title_suggestion=title_suggestion,
        content_type_to_use=content_type_to_use,
    )

    sections_in_order = _get_sections_in_order_for_blog_post(blog_post)
    section_titles_in_order = [
        (section.title or "").strip()
        for section in sections_in_order
        if (section.title or "").strip()
    ]

    intro_section = next(
        (
            section
            for section in sections_in_order
            if (section.title or "").strip() == INTRODUCTION_SECTION_TITLE
        ),
        None,
    )
    conclusion_section = next(
        (
            section
            for section in sections_in_order
            if (section.title or "").strip() == CONCLUSION_SECTION_TITLE
        ),
        None,
    )
    if not intro_section or not conclusion_section:
        raise ValueError(f"Blog post is missing Introduction/Conclusion sections: {blog_post_id}")

    should_generate_intro = not (intro_section.content or "").strip()
    should_generate_conclusion = not (conclusion_section.content or "").strip()
    if not should_generate_intro and not should_generate_conclusion:
        return 0

    middle_sections = [
        section
        for section in sections_in_order
        if (section.title or "").strip() not in NON_RESEARCH_SECTION_TITLES
    ]
    has_any_middle_section_missing_content = any(
        not (section.content or "").strip() for section in middle_sections
    )
    if has_any_middle_section_missing_content:
        logger.info(
            "[ContentGenerator] Skipping intro/conclusion generation; middle sections not ready",
            blog_post_id=blog_post.id,
            num_middle_sections=len(middle_sections),
        )
        return 0

    existing_sections_context = [
        PriorSectionContext(
            title=(section.title or "").strip(),
            content=(section.content or "").strip(),
        )
        for section in sections_in_order
        if (section.title or "").strip() and (section.content or "").strip()
    ]

    intro_conclusion_context = BlogPostIntroConclusionGenerationContext(
        blog_post_generation_context=blog_post_generation_context,
        blog_post_title=(blog_post.title or title_suggestion.title or "").strip(),
        section_titles_in_order=section_titles_in_order,
        sections_in_order=existing_sections_context,
    )

    agent = create_generate_blog_post_intro_conclusion_agent(content_type=content_type_to_use)
    result = run_agent_synchronously(
        agent,
        "Write the Introduction and Conclusion for this blog post.",
        deps=intro_conclusion_context,
        function_name="generate_intro_and_conclusion_for_blog_post.intro_conclusion",
        model_name="GeneratedBlogPostSection",
    )

    output: GeneratedBlogPostIntroConclusionSchema | None = (
        result.output if result and result.output else None
    )
    if not output:
        return 0

    num_sections_updated = 0
    if should_generate_intro:
        introduction_content = (output.introduction or "").strip()
        if introduction_content:
            intro_section.content = introduction_content
            intro_section.save(update_fields=["content"])
            num_sections_updated += 1

    if should_generate_conclusion:
        conclusion_content = (output.conclusion or "").strip()
        if conclusion_content:
            conclusion_section.content = conclusion_content
            conclusion_section.save(update_fields=["content"])
            num_sections_updated += 1

    logger.info(
        "[ContentGenerator] Intro/conclusion generated",
        blog_post_id=blog_post.id,
        intro_generated=bool((intro_section.content or "").strip()),
        conclusion_generated=bool((conclusion_section.content or "").strip()),
        num_sections_updated=num_sections_updated,
    )

    maybe_populate_generated_blog_post_content(blog_post_id=blog_post.id)
    return num_sections_updated


def maybe_queue_intro_conclusion_generation_for_blog_post(*, blog_post_id: int) -> bool:
    """
    Queue Step 6 only when all middle sections have content.

    Best-effort + idempotent: if it queues multiple times, the generation step skips when already present.
    """
    blog_post = (
        GeneratedBlogPost.objects.prefetch_related("blog_post_sections")
        .filter(id=blog_post_id)
        .first()
    )
    if not blog_post:
        return False

    sections_in_order = _get_sections_in_order_for_blog_post(blog_post)
    middle_sections = [
        section
        for section in sections_in_order
        if (section.title or "").strip() not in NON_RESEARCH_SECTION_TITLES
    ]

    if any(not (section.content or "").strip() for section in middle_sections):
        return False

    async_task(
        "core.content_generator.tasks.generate_intro_and_conclusion_for_blog_post_task",
        blog_post_id,
        group="Generate Intro and Conclusion",
    )
    logger.info(
        "[ContentGenerator] Queued intro/conclusion generation task",
        blog_post_id=blog_post_id,
        num_middle_sections=len(middle_sections),
    )
    return True


def _build_full_blog_post_markdown(*, blog_post: GeneratedBlogPost) -> str:
    blog_post_title = (blog_post.title or "").strip()
    if not blog_post_title:
        return ""

    sections_in_order = _get_sections_in_order_for_blog_post(blog_post)
    markdown_chunks = [f"# {blog_post_title}", ""]

    for section in sections_in_order:
        section_title = (section.title or "").strip()
        section_content = (section.content or "").strip()
        if not section_title or not section_content:
            continue

        markdown_chunks.append(f"## {section_title}")
        markdown_chunks.append("")
        markdown_chunks.append(section_content)
        markdown_chunks.append("")

    full_markdown = "\n".join(markdown_chunks).strip() + "\n"
    return full_markdown


def populate_generated_blog_post_content(*, blog_post_id: int) -> bool:
    """
    Step 7: Populate GeneratedBlogPost.content from the generated section contents.

    Runs only when:
    - All sections (including Introduction + Conclusion) have non-empty content
    - GeneratedBlogPost.content is currently empty
    """
    blog_post = (
        GeneratedBlogPost.objects.prefetch_related("blog_post_sections")
        .filter(id=blog_post_id)
        .first()
    )
    if not blog_post:
        raise ValueError(f"GeneratedBlogPost not found: {blog_post_id}")

    if (blog_post.content or "").strip():
        return False

    sections_in_order = _get_sections_in_order_for_blog_post(blog_post)
    if any(not (section.content or "").strip() for section in sections_in_order):
        logger.info(
            "[ContentGenerator] Skipping blog_post.content population; not all sections have content",
            blog_post_id=blog_post.id,
            num_sections=len(sections_in_order),
        )
        return False

    full_markdown = _build_full_blog_post_markdown(blog_post=blog_post)
    if not full_markdown.strip():
        logger.warning(
            "[ContentGenerator] Skipping blog_post.content population; built markdown is empty",
            blog_post_id=blog_post.id,
        )
        return False

    blog_post.content = full_markdown
    blog_post.save(update_fields=["content"])

    logger.info(
        "[ContentGenerator] Populated GeneratedBlogPost.content from sections",
        blog_post_id=blog_post.id,
        content_length=len(full_markdown),
    )
    return True


def maybe_populate_generated_blog_post_content(*, blog_post_id: int) -> bool:
    """
    Queue Step 7 when the whole pipeline is done.

    Best-effort + idempotent: population skips if blog_post.content is already non-empty.
    """
    blog_post = (
        GeneratedBlogPost.objects.prefetch_related("blog_post_sections")
        .filter(id=blog_post_id)
        .first()
    )
    if not blog_post:
        return False

    if (blog_post.content or "").strip():
        return False

    sections_in_order = _get_sections_in_order_for_blog_post(blog_post)
    if any(not (section.content or "").strip() for section in sections_in_order):
        return False

    async_task(
        "core.content_generator.tasks.populate_generated_blog_post_content_task",
        blog_post_id,
        group="Finalize Generated Blog Post Content",
    )
    logger.info(
        "[ContentGenerator] Queued blog_post.content population task",
        blog_post_id=blog_post_id,
        num_sections=len(sections_in_order),
    )
    return True
