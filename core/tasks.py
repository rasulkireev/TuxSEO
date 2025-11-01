import calendar
import json
import random
from urllib.parse import unquote

import posthog
import requests
from django.conf import settings
from django.utils import timezone
from django_q.tasks import async_task

from core.choices import ContentType, ProjectPageSource
from core.models import (
    BlogPostTitleSuggestion,
    Competitor,
    GeneratedBlogPost,
    Profile,
    Project,
    ProjectKeyword,
    ProjectPage,
)
from core.utils import save_keyword
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


def add_email_to_buttondown(email, tag):
    if not settings.BUTTONDOWN_API_KEY:
        return "Buttondown API key not found."

    data = {
        "email_address": str(email),
        "metadata": {"source": tag},
        "tags": [tag],
        "referrer_url": "https://tuxseo.app",
        "subscriber_type": "regular",
    }

    r = requests.post(
        "https://api.buttondown.email/v1/subscribers",
        headers={"Authorization": f"Token {settings.BUTTONDOWN_API_KEY}"},
        json=data,
    )

    return r.json()


def analyze_project_page(project_id: int, link: str):
    from django.core.exceptions import ValidationError

    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        logger.error(
            "[Analyze Project Page] Project not found",
            project_id=project_id,
        )
        return f"Project {project_id} not found"

    try:
        project_page, created = ProjectPage.objects.get_or_create(
            project=project, url=link, defaults={"source": ProjectPageSource.AI}
        )

        if created:
            logger.info(
                "[Analyze Project Page] Created new project page",
                project_id=project_id,
                project_name=project.name,
                page_url=link,
            )

            content_fetched = project_page.get_page_content()
            if not content_fetched:
                logger.warning(
                    "[Analyze Project Page] Failed to fetch page content, deleting page",
                    project_id=project_id,
                    project_name=project.name,
                    page_url=link,
                )
                project_page.delete()
                return f"Failed to fetch content for {link}, page deleted"

            project_page.analyze_content()
            logger.info(
                "[Analyze Project Page] Successfully analyzed page",
                project_id=project_id,
                project_name=project.name,
                page_url=link,
            )
        else:
            logger.info(
                "[Analyze Project Page] Page already exists, skipping",
                project_id=project_id,
                project_name=project.name,
                page_url=link,
            )

        return f"Analyzed {link} for {project.name}"

    except ValidationError as e:
        logger.error(
            "[Analyze Project Page] Invalid URL validation error",
            project_id=project_id,
            page_url=link,
            error=str(e),
        )
        # Try to find and delete the invalid page if it was created
        try:
            invalid_page = ProjectPage.objects.filter(project=project, url=link).first()
            if invalid_page:
                invalid_page.delete()
                logger.info(
                    "[Analyze Project Page] Deleted invalid page",
                    project_id=project_id,
                    page_url=link,
                )
        except Exception as delete_error:
            logger.error(
                "[Analyze Project Page] Failed to delete invalid page",
                project_id=project_id,
                page_url=link,
                error=str(delete_error),
                exc_info=True,
            )
        return f"Invalid URL validation error for {link}: {str(e)}"

    except Exception as e:
        logger.error(
            "[Analyze Project Page] Error analyzing page",
            project_id=project_id,
            page_url=link,
            error=str(e),
            exc_info=True,
        )
        return f"Error analyzing {link}: {str(e)}"


def schedule_project_page_analysis(project_id):
    project = Project.objects.get(id=project_id)

    try:
        project_links = project.get_a_list_of_links()
    except Exception as e:
        logger.error(
            "[Schedule Project Page Analysis] Failed to extract links",
            project_id=project_id,
            project_name=project.name,
            error=str(e),
            exc_info=True,
        )
        return f"Failed to extract links for {project.name}"

    if not project_links:
        logger.info(
            "[Schedule Project Page Analysis] No links found",
            project_id=project_id,
            project_name=project.name,
        )
        return f"No links found for {project.name}"

    count = 0
    for link in project_links:
        # Validate that the link is a proper URL
        if not link or not isinstance(link, str) or not link.startswith(("http://", "https://")):
            logger.warning(
                "[Schedule Project Page Analysis] Skipping invalid link",
                project_id=project_id,
                project_name=project.name,
                link=link,
            )
            continue

        async_task(
            analyze_project_page,
            project_id,
            link,
        )
        count += 1

    logger.info(
        "[Schedule Project Page Analysis] Scheduled page analysis",
        project_id=project_id,
        project_name=project.name,
        links_scheduled=count,
    )
    return f"Scheduled analysis for {count} links"


def schedule_project_competitor_analysis(project_id):
    project = Project.objects.get(id=project_id)
    competitors = project.find_competitors()
    if competitors:
        competitors = project.get_and_save_list_of_competitors()
        for competitor in competitors:
            async_task(analyze_project_competitor, competitor.id)

    return f"Saved Competitors for {project.name}"


def analyze_project_competitor(competitor_id):
    try:
        competitor = Competitor.objects.get(id=competitor_id)
    except Competitor.DoesNotExist:
        logger.error(
            "[Analyze Project Competitor] Competitor not found",
            competitor_id=competitor_id,
        )
        return f"Competitor {competitor_id} not found"

    try:
        got_content = competitor.get_page_content()

        if got_content:
            competitor.analyze_competitor()
            return f"Analyzed Competitor for {competitor.name}"
        else:
            logger.warning(
                "[Analyze Project Competitor] Failed to get page content",
                competitor_id=competitor_id,
                competitor_name=competitor.name,
            )
            return f"Failed to get content for competitor {competitor.name}"

    except Exception as e:
        logger.error(
            "[Analyze Project Competitor] Error analyzing competitor",
            competitor_id=competitor_id,
            competitor_name=competitor.name,
            error=str(e),
            exc_info=True,
        )
        return f"Error analyzing competitor {competitor.name}: {str(e)}"


def process_project_keywords(project_id: int):
    """
    Processes proposed keywords for a project:
    1. Saves them to the Keyword model.
    2. Fetches metrics for each keyword.
    3. Associates keywords with the project.
    """
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        logger.error(f"[KeywordProcessing] Project with id {project_id} not found.")
        return f"Project with id {project_id} not found."

    if not project.proposed_keywords:
        logger.info(
            f"[KeywordProcessing] No proposed keywords for project {project.id} ({project.name})."
        )
        return f"No proposed keywords for project {project.name}."

    keyword_strings = [kw.strip() for kw in project.proposed_keywords.split(",") if kw.strip()]
    processed_count = 0
    failed_count = 0

    for keyword_str in keyword_strings:
        try:
            save_keyword(keyword_str, project)
            processed_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(
                "[KeywordProcessing] Error processing keyword",
                error=str(e),
                exc_info=True,
                project_id=project.id,
                keyword_text=keyword_str,
            )

    logger.info(
        "Keyword Processing Complete",
        project_id=project.id,
        project_name=project.name,
        processed_count=processed_count,
        failed_count=failed_count,
    )

    async_task(get_and_save_related_keywords, project_id, group="Get Related Keywords")
    async_task(get_and_save_pasf_keywords, project_id, group="Get PASF Keywords")

    return f"""
    Keyword processing for project {project.name} (ID: {project.id})
    Processed {processed_count} keywords
    Failed: {failed_count}
    """


def generate_blog_post_suggestions(project_id: int):
    project = Project.objects.get(id=project_id)
    profile = project.profile

    if profile.reached_title_generation_limit:
        return "Title generation limit reached for free plan"

    project.generate_title_suggestions(content_type=ContentType.SHARING, num_titles=3)
    project.generate_title_suggestions(content_type=ContentType.SEO, num_titles=3)
    return "Blog post suggestions generated"


def try_create_posthog_alias(profile_id: int, cookies: dict, source_function: str = None) -> str:
    if not settings.POSTHOG_API_KEY:
        return "PostHog API key not found."

    base_log_data = {
        "profile_id": profile_id,
        "cookies": cookies,
        "source_function": source_function,
    }

    profile = Profile.objects.get(id=profile_id)
    email = profile.user.email

    base_log_data["email"] = email
    base_log_data["profile_id"] = profile_id

    posthog_cookie = cookies.get(f"ph_{settings.POSTHOG_API_KEY}_posthog")
    if not posthog_cookie:
        logger.warning("[Try Create Posthog Alias] No PostHog cookie found.", **base_log_data)
        return f"No PostHog cookie found for profile {profile_id}."
    base_log_data["posthog_cookie"] = posthog_cookie

    logger.info("[Try Create Posthog Alias] Setting PostHog alias", **base_log_data)

    cookie_dict = json.loads(unquote(posthog_cookie))
    frontend_distinct_id = cookie_dict.get("distinct_id")

    if frontend_distinct_id:
        posthog.alias(frontend_distinct_id, email)
        posthog.alias(frontend_distinct_id, str(profile_id))

    logger.info("[Try Create Posthog Alias] Set PostHog alias", **base_log_data)


def track_event(
    profile_id: int, event_name: str, properties: dict, source_function: str = None
) -> str:
    base_log_data = {
        "profile_id": profile_id,
        "event_name": event_name,
        "properties": properties,
        "source_function": source_function,
    }

    try:
        profile = Profile.objects.get(id=profile_id)
    except Profile.DoesNotExist:
        logger.error("[TrackEvent] Profile not found.", **base_log_data)
        return f"Profile with id {profile_id} not found."

    if settings.POSTHOG_API_KEY:
        posthog.capture(
            profile.user.email,
            event=event_name,
            properties={
                "profile_id": profile.id,
                "email": profile.user.email,
                "current_state": profile.state,
                **properties,
            },
        )

    logger.info("[TrackEvent] Tracked event", **base_log_data)

    return f"Tracked event {event_name} for profile {profile_id}"


def track_state_change(
    profile_id: int,
    from_state: str,
    to_state: str,
    metadata: dict = None,
    source_function: str = None,
) -> None:
    from core.models import Profile, ProfileStateTransition

    base_log_data = {
        "profile_id": profile_id,
        "from_state": from_state,
        "to_state": to_state,
        "metadata": metadata,
        "source_function": source_function,
    }

    try:
        profile = Profile.objects.get(id=profile_id)
    except Profile.DoesNotExist:
        logger.error("[TrackStateChange] Profile not found.", **base_log_data)
        return f"Profile with id {profile_id} not found."

    if from_state != to_state:
        logger.info("[TrackStateChange] Tracking state change", **base_log_data)
        ProfileStateTransition.objects.create(
            profile=profile,
            from_state=from_state,
            to_state=to_state,
            backup_profile_id=profile_id,
            metadata=metadata,
        )
        profile.state = to_state
        profile.save(update_fields=["state"])

    return f"Tracked state change from {from_state} to {to_state} for profile {profile_id}"


def schedule_blog_post_posting():
    now = timezone.now()
    projects = Project.objects.filter(enable_automatic_post_submission=True)

    scheduled_posts = 0
    for project in projects:
        if not project.has_auto_submission_setting or not project.profile.experimental_features:
            continue

        if not project.last_posted_blog_post:
            async_task(
                "core.tasks.generate_and_post_blog_post", project.id, group="Submit Blog Post"
            )
            scheduled_posts += 1
            continue

        last_post_date = project.last_posted_blog_post.date_posted
        time_since_last_post_in_seconds = (now - last_post_date).total_seconds()

        days_in_month = calendar.monthrange(now.year, now.month)[1]
        time_between_posts_in_seconds = int(
            days_in_month
            * (24 * 60 * 60)
            / project.auto_submission_settings.latest("created_at").posts_per_month
        )

        if time_since_last_post_in_seconds > time_between_posts_in_seconds:
            logger.info(
                "[Schedule Blog Post Posting] Scheduling blog post for {project.name}",
                project_id=project.id,
                project_name=project.name,
            )
            async_task(
                "core.tasks.generate_and_post_blog_post", project.id, group="Submit Blog Post"
            )
            scheduled_posts += 1

    return f"Scheduled {scheduled_posts} blog posts"


def generate_and_post_blog_post(project_id: int):
    project = Project.objects.get(id=project_id)
    profile = project.profile
    blog_post_to_post = None

    if not profile.has_auto_posting_enabled:
        return f"Auto-posting not available on {profile.product_name} plan"

    logger.info(
        "[Generate and Post Blog Post] Generating blog post for {project.name}",
        project_id=project_id,
        project_name=project.name,
    )

    # first see if there are generated blog posts that are not posted yet
    blog_posts_to_post = GeneratedBlogPost.objects.filter(project=project, posted=False)

    if blog_posts_to_post.exists():
        logger.info(
            "[Generate and Post Blog Post] Found BlogPost to posts for {project.name}",
            project_id=project_id,
            project_name=project.name,
        )
        blog_post_to_post = blog_posts_to_post.first()

    # then see if there are blog post title suggestions without generated blog posts
    if not blog_post_to_post:
        ungenerated_blog_post_suggestions = BlogPostTitleSuggestion.objects.filter(
            project=project, generated_blog_posts__isnull=True
        )
        if ungenerated_blog_post_suggestions.exists():
            logger.info(
                "[Generate and Post Blog Post] Found BlogPostTitleSuggestion to generate and post for {project.name}",  # noqa: E501
                project_id=project_id,
                project_name=project.name,
            )
            ungenerated_blog_post_suggestion = ungenerated_blog_post_suggestions.first()
            blog_post_to_post = ungenerated_blog_post_suggestion.generate_content(
                content_type=ungenerated_blog_post_suggestion.content_type
            )

    # if neither, create a new blog post title suggestion, generate the blog post
    if not blog_post_to_post:
        logger.info(
            "[Generate and Post Blog Post] No BlogPost or BlogPostTitleSuggestion found, so generating both.",  # noqa: E501
            project_id=project_id,
            project_name=project.name,
        )
        content_type = random.choice([choice[0] for choice in ContentType.choices])
        suggestions = project.generate_title_suggestions(content_type=content_type, num_titles=1)
        blog_post_to_post = suggestions[0].generate_content(
            content_type=suggestions[0].content_type
        )

    # once you have the generated blog post, submit it to the endpoint
    if blog_post_to_post:
        if blog_post_to_post.blog_post_content_is_valid is False:
            logger.info(
                "[Generate and Post Blog Post] Blog post content is not valid, so fixing it before posting.",  # noqa: E501
                project_id=project_id,
                project_name=project.name,
            )
            blog_post_to_post.fix_generated_blog_post()
            async_task(
                "core.tasks.generate_and_post_blog_post",
                project.id,
                group="Re-run Blog Post Generation/Posting",
            )
            return "Fixed blog post content and scheduled re-generation/posting."

        logger.info(
            "[Generate and Post Blog Post] Submitting blog post to endpoint",
            project_id=project_id,
            project_name=project.name,
            blog_post_title=blog_post_to_post.title,
        )
        result = blog_post_to_post.submit_blog_post_to_endpoint()
        if result is True:
            blog_post_to_post.posted = True
            blog_post_to_post.date_posted = timezone.now()
            blog_post_to_post.save(update_fields=["posted", "date_posted"])
            return f"Posted blog post for {project.name}"
        else:
            return f"Failed to post blog post for {project.name}."

    else:
        logger.error(
            "[Generate and Post Blog Post] No blog post to post. This should not happen.",
            project_id=project_id,
            project_name=project.name,
        )
        return f"No blog post to post for {project.name}."


def save_title_suggestion_keywords(title_suggestion_id: int):
    title_suggestion = BlogPostTitleSuggestion.objects.get(id=title_suggestion_id)

    if not title_suggestion.target_keywords or not title_suggestion.project:
        logger.warning(
            "[Save Title Suggestion Keywords] No target keywords or project found",
            title_suggestion_id=title_suggestion_id,
            has_keywords=bool(title_suggestion.target_keywords),
            has_project=bool(title_suggestion.project),
        )
        return "No keywords or project to save"

    saved_keywords_count = 0
    for keyword_text in title_suggestion.target_keywords:
        if keyword_text and keyword_text.strip():
            save_keyword(keyword_text.strip(), title_suggestion.project)
            saved_keywords_count += 1

    logger.info(
        "[Save Title Suggestion Keywords] Successfully saved keywords",
        title_suggestion_id=title_suggestion_id,
        project_id=title_suggestion.project_id,
        project_name=title_suggestion.project.name,
        saved_keywords_count=saved_keywords_count,
        total_keywords=len(title_suggestion.target_keywords),
    )

    return f"Saved {saved_keywords_count} keywords for project {title_suggestion.project.name}"


def get_and_save_related_keywords(
    project_id: int,
    limit: int = 10,
    num_related_keywords: int = 5,
    volume_threshold: int = 10000,
):
    """
    Expands project keywords by finding and saving related keywords from Keywords Everywhere API.

    Process:
    1. Finds high-volume keywords (>volume_threshold) that haven't been processed yet
    2. For each keyword, calls Keywords Everywhere API to get related keywords
    3. Saves each related keyword to database with metrics and project association
    4. Marks parent keyword as processed to avoid duplicate API calls

    Args:
        project_id: ID of the project to process keywords for
        limit: Maximum number of parent keywords to process (default: 10)
        num_related_keywords: Number of related keywords to request per keyword (default: 5)
        volume_threshold: Minimum search volume for parent keywords (default: 10000)

    Returns:
        String summary of processing results
    """
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        logger.error(f"[GetRelatedKeywords] Project {project_id} not found.")
        return f"Project {project_id} not found."

    keywords_to_process = ProjectKeyword.objects.filter(
        project=project,
        keyword__volume__gt=volume_threshold,
        keyword__volume__isnull=False,
        keyword__got_related_keywords=False,
    ).select_related("keyword")[:limit]

    if not keywords_to_process.exists():
        return f"No unprocessed high-volume keywords found for {project.name}."

    stats = {
        "processed": 0,
        "failed": 0,
        "total": keywords_to_process.count(),
        "credits_used": 0,
        "related_found": 0,
        "related_saved": 0,
    }

    logger.info(f"[GetRelatedKeywords] Processing {stats['total']} keywords for {project.name}")

    api_url = "https://api.keywordseverywhere.com/v1/get_related_keywords"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.KEYWORDS_EVERYWHERE_API_KEY}",
    }

    for project_keyword in keywords_to_process:
        keyword = project_keyword.keyword

        try:
            response = requests.post(
                api_url,
                data={"keyword": keyword.keyword_text, "num": num_related_keywords},
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                related_keywords = data.get("data", [])
                stats["credits_used"] += data.get("credits_consumed", 0)
                stats["related_found"] += len(related_keywords)
                stats["processed"] += 1

                for keyword_text in related_keywords:
                    if keyword_text and keyword_text.strip():
                        try:
                            save_keyword(keyword_text.strip(), project)
                            stats["related_saved"] += 1
                        except Exception as e:
                            logger.error(
                                "[GetRelatedKeywords] Failed to save keyword",
                                keyword_text=keyword_text,
                                error=str(e),
                                exc_info=True,
                            )

                keyword.got_related_keywords = True
                keyword.save(update_fields=["got_related_keywords"])

            else:
                stats["failed"] += 1
                logger.warning(
                    "[GetRelatedKeywords] API error for Keyword",
                    keyword_text=keyword.keyword_text,
                    response_status_code=response.status_code,
                    exc_info=True,
                )

        except Exception as e:
            stats["failed"] += 1
            logger.error(
                "[GetRelatedKeywords] Error processing Keyword",
                keyword_text=keyword.keyword_text,
                error=str(e),
                exc_info=True,
            )

    logger.info(
        "[GetRelatedKeywords] Completed",
        project_id=project_id,
        project_name=project.name,
        processed=stats["processed"],
        total=stats["total"],
        failed=stats["failed"],
        credits_used=stats["credits_used"],
        related_found=stats["related_found"],
        related_saved=stats["related_saved"],
    )

    return f"""Related Keywords Processing Results for {project.name}:
    Keywords processed: {stats["processed"]}/{stats["total"]}
    Failed: {stats["failed"]}
    API credits used: {stats["credits_used"]}
    Related keywords found: {stats["related_found"]}
    Related keywords saved: {stats["related_saved"]}"""


def get_and_save_pasf_keywords(
    project_id: int,
    limit: int = 10,
    num_pasf_keywords: int = 5,
    volume_threshold: int = 10000,
):
    """
    Expands project keywords by finding and saving "People Also Search For"
    keywords from Keywords Everywhere API.

    Process:
    1. Finds high-volume keywords (>volume_threshold) that haven't been processed for PASF yet
    2. For each keyword, calls Keywords Everywhere PASF API to get related search queries
    3. Saves each PASF keyword to database with metrics and project association
    4. Marks parent keyword as processed to avoid duplicate API calls

    Args:
        project_id: ID of the project to process keywords for
        limit: Maximum number of parent keywords to process (default: 10)
        num_pasf_keywords: Number of PASF keywords to request per keyword (default: 5)
        volume_threshold: Minimum search volume for parent keywords (default: 10000)

    Returns:
        String summary of processing results
    """
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        logger.error(f"[GetPASFKeywords] Project {project_id} not found.")
        return f"Project {project_id} not found."

    keywords_to_process = ProjectKeyword.objects.filter(
        project=project,
        keyword__volume__gt=volume_threshold,
        keyword__volume__isnull=False,
        keyword__got_people_also_search_for_keywords=False,
    ).select_related("keyword")[:limit]

    if not keywords_to_process.exists():
        return f"No unprocessed high-volume keywords found for PASF processing in {project.name}."

    stats = {
        "processed": 0,
        "failed": 0,
        "total": keywords_to_process.count(),
        "credits_used": 0,
        "pasf_found": 0,
        "pasf_saved": 0,
    }

    logger.info(f"[GetPASFKeywords] Processing {stats['total']} keywords for {project.name}")

    api_url = "https://api.keywordseverywhere.com/v1/get_pasf_keywords"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.KEYWORDS_EVERYWHERE_API_KEY}",
    }

    for project_keyword in keywords_to_process:
        keyword = project_keyword.keyword

        try:
            response = requests.post(
                api_url,
                data={"keyword": keyword.keyword_text, "num": num_pasf_keywords},
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                pasf_keywords = data.get("data", [])
                stats["credits_used"] += data.get("credits_consumed", 0)
                stats["pasf_found"] += len(pasf_keywords)
                stats["processed"] += 1

                for keyword_text in pasf_keywords:
                    if keyword_text and keyword_text.strip():
                        try:
                            save_keyword(keyword_text.strip(), project)
                            stats["pasf_saved"] += 1
                        except Exception as e:
                            logger.error(
                                "[GetPASFKeywords] Failed to save keyword",
                                keyword_text=keyword_text,
                                error=str(e),
                                exc_info=True,
                            )

                keyword.got_people_also_search_for_keywords = True
                keyword.save(update_fields=["got_people_also_search_for_keywords"])

            else:
                stats["failed"] += 1
                logger.warning(
                    "[GetPASFKeywords] API error for Keyword",
                    keyword_text=keyword.keyword_text,
                    response_status_code=response.status_code,
                    response_content=response.content.decode("utf-8")
                    if response.content
                    else "No content",
                    exc_info=True,
                )

        except Exception as e:
            stats["failed"] += 1
            logger.error(
                "[GetPASFKeywords] Error processing Keyword",
                keyword_text=keyword.keyword_text,
                error=str(e),
                exc_info=True,
            )

    logger.info(
        f"[GetPASFKeywords] Completed: {stats['processed']}/{stats['total']} keywords processed"
    )

    return f"""PASF Keywords Processing Results for {project.name}:
    Keywords processed: {stats["processed"]}/{stats["total"]}
    Failed: {stats["failed"]}
    API credits used: {stats["credits_used"]}
    PASF keywords found: {stats["pasf_found"]}
    PASF keywords saved: {stats["pasf_saved"]}"""


def parse_sitemap_and_save_urls(project_id: int):
    """
    Parse the project's sitemap and save all URLs as ProjectPage records with SITEMAP source.
    This task is called immediately when a user adds a sitemap URL.
    """
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        logger.error(f"[Parse Sitemap] Project {project_id} not found.")
        return f"Project {project_id} not found."

    if not project.sitemap_url:
        logger.warning(
            "[Parse Sitemap] No sitemap URL found for project",
            project_id=project_id,
            project_name=project.name,
        )
        return f"No sitemap URL found for project {project.name}."

    logger.info(
        "[Parse Sitemap] Starting sitemap parsing",
        project_id=project_id,
        project_name=project.name,
        sitemap_url=project.sitemap_url,
    )

    try:
        response = requests.get(project.sitemap_url, timeout=30)
        response.raise_for_status()

        # Parse XML content
        import xml.etree.ElementTree as ET

        root = ET.fromstring(response.content)

        # Handle both sitemap formats: standard sitemap and sitemap index
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        urls_found = []

        # Check if this is a sitemap index
        sitemap_locs = root.findall(".//ns:sitemap/ns:loc", namespace)
        if sitemap_locs:
            # This is a sitemap index, fetch each sitemap
            for sitemap_loc in sitemap_locs:
                sitemap_url = sitemap_loc.text
                try:
                    sitemap_response = requests.get(sitemap_url, timeout=30)
                    sitemap_response.raise_for_status()
                    sitemap_root = ET.fromstring(sitemap_response.content)
                    url_locs = sitemap_root.findall(".//ns:url/ns:loc", namespace)
                    urls_found.extend([loc.text for loc in url_locs if loc.text])
                except Exception as e:
                    logger.warning(
                        "[Parse Sitemap] Failed to fetch nested sitemap",
                        sitemap_url=sitemap_url,
                        error=str(e),
                    )
        else:
            # This is a regular sitemap
            url_locs = root.findall(".//ns:url/ns:loc", namespace)
            urls_found.extend([loc.text for loc in url_locs if loc.text])

        # Save URLs to database
        created_count = 0
        existing_count = 0

        for url in urls_found:
            project_page, created = ProjectPage.objects.get_or_create(
                project=project, url=url, defaults={"source": ProjectPageSource.SITEMAP}
            )
            if created:
                created_count += 1
            else:
                existing_count += 1

        logger.info(
            "[Parse Sitemap] Completed sitemap parsing",
            project_id=project_id,
            project_name=project.name,
            total_urls=len(urls_found),
            created_count=created_count,
            existing_count=existing_count,
        )

        # Schedule analysis of first 10 unanalyzed pages
        async_task(
            "core.tasks.analyze_sitemap_pages",
            project_id,
            group="Analyze Sitemap Pages",
        )

        return f"""Sitemap parsing completed for {project.name}:
        Total URLs found: {len(urls_found)}
        New pages: {created_count}
        Existing pages: {existing_count}"""

    except requests.RequestException as e:
        logger.error(
            "[Parse Sitemap] Request error",
            project_id=project_id,
            project_name=project.name,
            sitemap_url=project.sitemap_url,
            error=str(e),
            exc_info=True,
        )
        return f"Failed to fetch sitemap for {project.name}: {str(e)}"
    except Exception as e:
        logger.error(
            "[Parse Sitemap] Unexpected error",
            project_id=project_id,
            project_name=project.name,
            error=str(e),
            exc_info=True,
        )
        return f"Error parsing sitemap for {project.name}: {str(e)}"


def analyze_sitemap_pages(project_id: int, limit: int = 10):
    """
    Analyze up to 'limit' unanalyzed project pages from sitemap for a project.
    This fetches page content and generates summaries.
    """
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        logger.error(f"[Analyze Sitemap Pages] Project {project_id} not found.")
        return f"Project {project_id} not found."

    # Get unanalyzed pages from sitemap source (pages without date_analyzed)
    unanalyzed_pages = ProjectPage.objects.filter(
        project=project,
        source=ProjectPageSource.SITEMAP,
        date_analyzed__isnull=True,
    ).order_by("created_at")[:limit]

    if not unanalyzed_pages.exists():
        logger.info(
            "[Analyze Sitemap Pages] No unanalyzed pages found",
            project_id=project_id,
            project_name=project.name,
        )
        return f"No unanalyzed sitemap pages found for {project.name}."

    stats = {
        "total": unanalyzed_pages.count(),
        "analyzed": 0,
        "failed": 0,
    }

    logger.info(
        "[Analyze Sitemap Pages] Starting analysis",
        project_id=project_id,
        project_name=project.name,
        pages_to_analyze=stats["total"],
    )

    for project_page in unanalyzed_pages:
        try:
            # Fetch page content
            content_fetched = project_page.get_page_content()

            if content_fetched:
                # Analyze and summarize
                project_page.analyze_content()
                stats["analyzed"] += 1
                logger.info(
                    "[Analyze Sitemap Pages] Page analyzed successfully",
                    project_id=project_id,
                    project_page_id=project_page.id,
                    url=project_page.url,
                )
            else:
                stats["failed"] += 1
                logger.warning(
                    "[Analyze Sitemap Pages] Failed to fetch content, deleting page",
                    project_id=project_id,
                    project_page_id=project_page.id,
                    url=project_page.url,
                )
                # Delete the page if we can't fetch content
                project_page.delete()

        except Exception as e:
            stats["failed"] += 1
            logger.error(
                "[Analyze Sitemap Pages] Error analyzing page, deleting",
                project_id=project_id,
                project_page_id=project_page.id,
                url=project_page.url,
                error=str(e),
                exc_info=True,
            )
            # Delete pages that cause errors during analysis
            try:
                project_page.delete()
            except Exception as delete_error:
                logger.error(
                    "[Analyze Sitemap Pages] Failed to delete page after analysis error",
                    project_id=project_id,
                    project_page_id=project_page.id,
                    url=project_page.url,
                    error=str(delete_error),
                    exc_info=True,
                )

    logger.info(
        "[Analyze Sitemap Pages] Completed analysis",
        project_id=project_id,
        project_name=project.name,
        total=stats["total"],
        analyzed=stats["analyzed"],
        failed=stats["failed"],
    )

    return f"""Sitemap page analysis for {project.name}:
    Pages analyzed: {stats["analyzed"]}/{stats["total"]}
    Failed: {stats["failed"]}"""


def analyze_project_sitemap_pages_daily():
    """
    Daily scheduled task that checks all projects with sitemap URLs
    and schedules analysis for any unanalyzed pages (10 at a time per project).
    """
    projects_with_sitemaps = Project.objects.exclude(sitemap_url="")

    scheduled_count = 0

    for project in projects_with_sitemaps:
        # Check if there are unanalyzed pages from sitemap
        unanalyzed_count = ProjectPage.objects.filter(
            project=project,
            source=ProjectPageSource.SITEMAP,
            date_analyzed__isnull=True,
        ).count()

        if unanalyzed_count > 0:
            logger.info(
                "[Daily Sitemap Analysis] Scheduling analysis",
                project_id=project.id,
                project_name=project.name,
                unanalyzed_count=unanalyzed_count,
            )

            async_task(
                "core.tasks.analyze_sitemap_pages",
                project.id,
                group="Daily Sitemap Analysis",
            )
            scheduled_count += 1

    logger.info(
        "[Daily Sitemap Analysis] Completed scheduling",
        total_projects_with_sitemaps=projects_with_sitemaps.count(),
        scheduled_projects=scheduled_count,
    )

    return f"""Daily sitemap analysis check completed:
    Projects with sitemaps: {projects_with_sitemaps.count()}
    Projects scheduled for analysis: {scheduled_count}"""
