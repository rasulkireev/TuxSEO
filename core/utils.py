import posthog
from django.conf import settings
from django.forms.utils import ErrorList

from core.choices import KeywordDataSource
from core.models import Keyword, Profile, Project, ProjectKeyword
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


def check_blog_post_before_sending(blog_post):
    """
    Validate a blog post before sending it to an endpoint.
    
    Args:
        blog_post: The GeneratedBlogPost instance to validate
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
        
    Raises:
        ValueError: If blog_post is None or missing required attributes
    """
    if not blog_post:
        raise ValueError("Blog post cannot be None")
    
    if not hasattr(blog_post, "content"):
        raise ValueError("Blog post must have a content attribute")
    
    # Check if content exists and has sufficient length
    content = blog_post.content or ""
    
    if len(content.strip()) < 3000:
        return False, f"Blog post content is too short ({len(content.strip())} characters). Minimum required: 3000 characters."
    
    # Future checks can be added here
    # For example:
    # - Check for required sections
    # - Validate image presence
    # - Check for proper formatting
    # - Validate SEO requirements
    
    return True, None
