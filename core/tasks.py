import calendar
import json
import random
from urllib.parse import unquote

import posthog
import requests
from django.conf import settings
from django.utils import timezone
from django_q.tasks import async_task

from core.choices import ContentType
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
    project = Project.objects.get(id=project_id)
    project_page, created = ProjectPage.objects.get_or_create(project=project, url=link)

    if created:
        project_page.get_page_content()
        project_page.analyze_content()

    return f"Analyzed {link} for {project.name}"


def schedule_project_page_analysis(project_id):
    project = Project.objects.get(id=project_id)
    project_links = project.get_a_list_of_links()

    count = 0
    for link in project_links:
        async_task(
            analyze_project_page,
            project_id,
            link,
        )
        count += 1

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
    competitor = Competitor.objects.get(id=competitor_id)
    got_content = competitor.get_page_content()

    if got_content:
        competitor.analyze_competitor()

    return f"Analyzed Competitor for {competitor.name}"


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
    blog_post_to_post = None

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
            "[Generate and Post Blog Post] No BlogPost or BlogPostTitleSuggestion found for {project.name}, so generatin both.",  # noqa: E501
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
        logger.info(
            "[Generate and Post Blog Post] Submitting blog post to endpoint for {project.name}",
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
        return f"No blog post to post for {project.name}."


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
