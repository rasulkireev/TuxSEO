import re

import posthog
from django.conf import settings
from django.forms.utils import ErrorList
from pydantic_ai import Agent

from core.choices import EmailType, KeywordDataSource, get_default_ai_model
from core.constants import PLACEHOLDER_BRACKET_PATTERNS, PLACEHOLDER_PATTERNS
from core.model_utils import run_agent_synchronously
from core.models import EmailSent, GeneratedBlogPost, Keyword, Profile, Project, ProjectKeyword
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


class DivErrorList(ErrorList):
    def __str__(self):
        return self.as_divs()

    def as_divs(self):
        if not self:
            return ""
        return f"""
            <div class="p-4 my-4 bg-red-50 rounded-md border border-red-600 border-solid">
              <div class="flex">
                <div class="flex-shrink-0">
                  <!-- Heroicon name: solid/x-circle -->
                  <svg class="w-5 h-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                  </svg>
                </div>
                <div class="ml-3 text-sm text-red-700">
                      {"".join([f"<p>{e}</p>" for e in self])}
                </div>
              </div>
            </div>
         """  # noqa: E501


def replace_placeholders(data, blog_post):
    """
    Recursively replace values in curly braces (e.g., '{{ slug }}')
    in a dict with the corresponding attribute from blog_post.
    """
    if isinstance(data, dict):
        return {k: replace_placeholders(v, blog_post) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_placeholders(item, blog_post) for item in data]
    elif isinstance(data, str):
        import re

        def repl(match):
            attr = match.group(1).strip()
            # Support nested attributes (e.g., title.title)
            value = blog_post
            for part in attr.split("."):
                value = getattr(value, part, match.group(0))
                if value == match.group(0):
                    break
            return str(value)

        return re.sub(r"\{\{\s*(.*?)\s*\}\}", repl, data)
    else:
        return data


def get_or_create_project(profile_id, url, source=None):
    profile = Profile.objects.get(id=profile_id)
    project, created = Project.objects.get_or_create(profile=profile, url=url)

    project_metadata = {
        "source": source,
        "profile_id": profile_id,
        "profile_email": profile.user.email,
        "project_id": project.id,
        "project_name": project.name,
        "project_url": url,
    }

    if created:
        if settings.POSTHOG_API_KEY:
            posthog.capture(
                profile.user.email,
                event="project_created",
                properties=project_metadata,
            )
        logger.info("[Get or Create Project] Project created", **project_metadata)
    else:
        logger.info("[Get or Create Project] Got existing project", **project_metadata)

    return project


def save_keyword(keyword_text: str, project: Project):
    """Helper function to save a related keyword with metrics and project association."""
    keyword_obj, created = Keyword.objects.get_or_create(
        keyword_text=keyword_text,
        country="us",
        data_source=KeywordDataSource.GOOGLE_KEYWORD_PLANNER,
    )

    # Fetch metrics if newly created
    if created:
        metrics_fetched = keyword_obj.fetch_and_update_metrics()
        if not metrics_fetched:
            logger.warning(
                "[Save Keyword] Failed to fetch metrics for keyword",
                keyword_id=keyword_obj.id,
                keyword_text=keyword_text,
            )

    # Associate with project
    ProjectKeyword.objects.get_or_create(project=project, keyword=keyword_obj)


def blog_post_has_placeholders(blog_post: GeneratedBlogPost) -> bool:
    content = blog_post.content or ""
    content_lower = content.lower()

    for pattern in PLACEHOLDER_PATTERNS:
        if pattern in content_lower:
            logger.warning(
                "[Blog Post Has Placeholders] Placeholder found",
                pattern=pattern,
                blog_post_id=blog_post.id,
            )
            return True

    for pattern in PLACEHOLDER_BRACKET_PATTERNS:
        matches = re.findall(pattern, content_lower)
        if matches:
            logger.warning(
                "[Blog Post Has Placeholders] Bracket Placeholder found",
                pattern=pattern,
                blog_post_id=blog_post.id,
            )
            return True

    logger.info(
        "[Blog Post Has Placeholders] No placeholders found",
        blog_post_id=blog_post.id,
    )

    return False


def get_project_keywords_dict(project: Project) -> dict:
    """
    Build a dictionary of project keywords for quick lookup.

    Returns a dict mapping lowercase keyword text to keyword metadata:
    {
        "keyword_text": {
            "keyword": Keyword object,
            "in_use": bool,
            "project_keyword_id": int
        }
    }
    """
    project_keywords = {}
    for project_keyword in project.project_keywords.select_related("keyword").all():
        project_keywords[project_keyword.keyword.keyword_text.lower()] = {
            "keyword": project_keyword.keyword,
            "in_use": project_keyword.use,
            "project_keyword_id": project_keyword.id,
        }
    return project_keywords


def blog_post_has_valid_ending(blog_post: GeneratedBlogPost) -> bool:
    content = blog_post.content
    content = content.strip()

    agent = Agent(
        get_default_ai_model(),
        output_type=bool,
        system_prompt="""
        You are an expert content editor analyzing blog post endings. Your task is to determine
        whether the provided text represents a complete, proper conclusion to a blog post.

        A valid blog post ending should:
        - Complete the final thought or sentence
        - Provide closure to the topic being discussed
        - Feel like a natural conclusion (not abruptly cut off)
        - May include calls-to-action, summaries, or closing remarks

        An invalid ending would be:
        - Cut off mid-sentence
        - Ending abruptly without proper conclusion
        - Incomplete thoughts or paragraphs
        - Missing expected closing elements for the content type

        Analyze the text carefully and provide your assessment. Return True if the ending is valid, False if not.
        """,  # noqa: E501
        retries=2,
        model_settings={"temperature": 0.1},  # Lower temperature for more consistent analysis
    )

    try:
        result = run_agent_synchronously(
            agent,
            f"Please analyze this blog post and determine if it has a complete ending:\n\n{content}",  # noqa: E501
            function_name="blog_post_has_valid_ending",
        )

        ending_is_valid = result.data

        if ending_is_valid:
            logger.info(
                "[Blog Post Has Valid Ending] Valid ending",
                result=ending_is_valid,
                blog_post_id=blog_post.id,
            )
        else:
            logger.warning(
                "[Blog Post Has Valid Ending] Invalid ending",
                result=ending_is_valid,
                blog_post_id=blog_post.id,
            )

        return ending_is_valid

    except Exception as e:
        logger.error(
            "[Blog Post Has Valid Ending] AI analysis failed",
            error=str(e),
            exc_info=True,
            content_length=len(content),
        )
        return False


def blog_post_starts_with_header(blog_post: GeneratedBlogPost) -> bool:
    content = blog_post.content or ""
    content = content.strip()

    if not content:
        return False

    header_or_asterisk_pattern = r"^(#{1,6}\s+|\*)"
    starts_with_header_or_asterisk = bool(re.match(header_or_asterisk_pattern, content))

    if starts_with_header_or_asterisk:
        logger.warning(
            "[Blog Post Starts With Header] Content starts with header or asterisk",
            blog_post_id=blog_post.id,
        )
    else:
        logger.info(
            "[Blog Post Starts With Header] Content starts with regular text",
            blog_post_id=blog_post.id,
        )

    return starts_with_header_or_asterisk


def track_email_sent(email_address: str, email_type: EmailType, profile: Profile = None):
    """
    Track sent emails by creating EmailSent records.
    """
    try:
        email_sent = EmailSent.objects.create(
            email_address=email_address, email_type=email_type, profile=profile
        )
        logger.info(
            "[Track Email Sent] Email tracked successfully",
            email_address=email_address,
            email_type=email_type,
            profile_id=profile.id if profile else None,
            email_sent_id=email_sent.id,
        )
        return email_sent
    except Exception as e:
        logger.error(
            "[Track Email Sent] Failed to track email",
            email_address=email_address,
            email_type=email_type,
            error=str(e),
            exc_info=True,
        )
        return None
