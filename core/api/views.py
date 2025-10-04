from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from ninja import NinjaAPI

from core.api.auth import session_auth, superuser_api_auth
from core.api.schemas import (
    AddCompetitorIn,
    AddKeywordIn,
    AddKeywordOut,
    AddPricingPageIn,
    BlogPostIn,
    BlogPostOut,
    CompetitorAnalysisOut,
    DeleteProjectKeywordIn,
    DeleteProjectKeywordOut,
    GeneratedContentOut,
    GenerateTitleSuggestionOut,
    GenerateTitleSuggestionsIn,
    GenerateTitleSuggestionsOut,
    PostGeneratedBlogPostIn,
    PostGeneratedBlogPostOut,
    ProjectScanIn,
    ProjectScanOut,
    SubmitFeedbackIn,
    ToggleAutoSubmissionOut,
    ToggleProjectKeywordUseIn,
    ToggleProjectKeywordUseOut,
    UpdateArchiveStatusIn,
    UpdateTitleScoreIn,
    UserSettingsOut,
)
from core.choices import ContentType, ProjectPageType
from core.models import (
    BlogPost,
    BlogPostTitleSuggestion,
    Competitor,
    Feedback,
    GeneratedBlogPost,
    Keyword,
    Project,
    ProjectKeyword,
    ProjectPage,
)
from core.utils import get_or_create_project
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)

api = NinjaAPI(docs_url=None)


@api.post("/scan", response=ProjectScanOut, auth=[session_auth])
def scan_project(request: HttpRequest, data: ProjectScanIn):
    profile = request.auth

    # TODO(Rasul): Why do we need this?
    project = Project.objects.filter(profile=profile, url=data.url).first()
    if project:
        return {
            "status": "success",
            "project_id": project.id,
            "has_details": bool(project.name),
            "has_suggestions": project.blog_post_title_suggestions.exists(),
        }

    if Project.objects.filter(url=data.url).exists():
        return {
            "status": "error",
            "message": "Project already exists",
        }

    project = get_or_create_project(profile.id, data.url, source="scan_project")

    got_content = project.get_page_content()

    analyzed_project = False
    if got_content:
        analyzed_project = project.analyze_content()
    else:
        project.delete()
        return {
            "status": "error",
            "message": "Failed to get page content",
        }

    if analyzed_project:
        return {
            "status": "success",
            "project_id": project.id,
            "name": project.name,
            "type": project.get_type_display(),
            "url": project.url,
            "summary": project.summary,
        }
    else:
        logger.error(
            "[Scan Project] Project has no content",
            got_content=got_content,
            analyzed_project=analyzed_project,
            project_id=project.id if project else None,
            url=data.url,
        )
        project.delete()
        return {
            "status": "error",
            "message": "Failed to analyze project",
        }


@api.post("/generate-title-suggestions", response=GenerateTitleSuggestionsOut, auth=[session_auth])
def generate_title_suggestions(request: HttpRequest, data: GenerateTitleSuggestionsIn):
    profile = request.auth
    project = get_object_or_404(Project, id=data.project_id, profile=profile)

    try:
        content_type = ContentType[data.content_type]
    except KeyError:
        return {
            "suggestions": [],
            "suggestions_html": [],
            "status": "error",
            "message": f"Invalid content type: {data.content_type}",
        }

    if (
        profile.number_of_title_suggestions + data.num_titles >= 20
        and not profile.has_active_subscription
    ):
        return {
            "suggestions": [],
            "suggestions_html": [],
            "status": "error",
            "message": "Title generation limit reached. Consider <a class='underline' href='/pricing'>upgrading</a>?",  # noqa: E501
        }

    suggestions = project.generate_title_suggestions(
        content_type=content_type, num_titles=data.num_titles
    )

    # Render HTML for each suggestion using the Django template
    suggestions_html = []
    for suggestion in suggestions:
        context = {
            "suggestion": suggestion,
            "has_pro_subscription": profile.has_active_subscription,
            "has_auto_submission_setting": project.has_auto_submission_setting,
        }
        html = render_to_string("components/blog_post_suggestion_card.html", context)
        suggestions_html.append(html)

    return {
        "suggestions": suggestions,
        "suggestions_html": suggestions_html,
        "status": "success",
        "message": "",
    }


@api.post("/generate-title-from-idea", response=GenerateTitleSuggestionOut, auth=[session_auth])
def generate_title_from_idea(request: HttpRequest, data: GenerateTitleSuggestionsIn):
    profile = request.auth
    project = get_object_or_404(Project, id=data.project_id, profile=profile)

    if profile.reached_title_generation_limit:
        return {
            "status": "error",
            "message": "Title generation limit reached. Consider <a class='underline' href='/pricing'>upgrading</a>?",  # noqa: E501
        }

    try:
        try:
            content_type = ContentType[data.content_type]
        except KeyError:
            return {"status": "error", "message": f"Invalid content type: {data.content_type}"}

        suggestions = project.generate_title_suggestions(
            content_type=content_type, num_titles=1, user_prompt=data.user_prompt
        )

        if not suggestions:
            return {"status": "error", "message": "No suggestions were generated"}

        suggestion = suggestions[0]

        # Render HTML for the suggestion using the Django template
        context = {
            "suggestion": suggestion,
            "has_pro_subscription": profile.has_active_subscription,
            "has_auto_submission_setting": project.has_auto_submission_setting,
        }
        suggestion_html = render_to_string("components/blog_post_suggestion_card.html", context)

        return {
            "status": "success",
            "suggestion": {
                "id": suggestion.id,
                "title": suggestion.title,
                "description": suggestion.description,
                "category": suggestion.category,
                "target_keywords": suggestion.target_keywords,
                "suggested_meta_description": suggestion.suggested_meta_description,
                "content_type": suggestion.content_type,
            },
            "suggestion_html": suggestion_html,
        }

    except Exception as e:
        logger.error(
            "Failed to generate title from idea",
            error=str(e),
            project_id=project.id,
            user_prompt=data.user_prompt,
        )
        raise e


@api.post(
    "/generate-blog-content/{suggestion_id}", response=GeneratedContentOut, auth=[session_auth]
)
def generate_blog_content(request: HttpRequest, suggestion_id: int):
    profile = request.auth
    suggestion = get_object_or_404(
        BlogPostTitleSuggestion, id=suggestion_id, project__profile=profile
    )

    if profile.reached_content_generation_limit:
        return {
            "status": "error",
            "message": "Content generation limit reached. Consider <a class='underline' href='/pricing'>upgrading</a>?",  # noqa: E501
        }

    try:
        blog_post = suggestion.generate_content(content_type=suggestion.content_type)

        if not blog_post or not blog_post.content:
            return {"status": "error", "message": "Failed to generate content. Please try again."}

        return {
            "status": "success",
            "id": blog_post.id,
            "content": blog_post.content,
            "slug": blog_post.slug,
            "tags": blog_post.tags,
            "description": blog_post.description,
        }

    except ValueError as e:
        logger.error(
            "Failed to generate blog content",
            error=str(e),
            suggestion_id=suggestion_id,
            profile_id=profile.id,
        )
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(
            "Unexpected error generating blog content",
            error=str(e),
            exc_info=True,
            suggestion_id=suggestion_id,
            profile_id=profile.id,
        )
        return {
            "status": "error",
            "message": "An unexpected error occurred. Please try again later.",
        }


@api.post("/projects/{project_id}/update", response={200: dict}, auth=[session_auth])
def update_project(request: HttpRequest, project_id: int):
    profile = request.auth
    logger.info("Updating project", project_id=project_id, profile_id=profile.id)
    project = get_object_or_404(Project, id=project_id, profile=profile)

    # Update project fields from form data
    project.key_features = request.POST.get("key_features", "")
    project.target_audience_summary = request.POST.get("target_audience_summary", "")
    project.pain_points = request.POST.get("pain_points", "")
    project.product_usage = request.POST.get("product_usage", "")
    project.links = request.POST.get("links", "")
    project.blog_theme = request.POST.get("blog_theme", "")
    project.founders = request.POST.get("founders", "")
    project.language = request.POST.get("language", "")

    project.save()

    return {"status": "success"}


@api.post(
    "/projects/{project_id}/toggle-auto-submission",
    response=ToggleAutoSubmissionOut,
    auth=[session_auth],
)
def toggle_auto_submission(request: HttpRequest, project_id: int):
    profile = request.auth
    project = get_object_or_404(Project, id=project_id, profile=profile)

    project.enable_automatic_post_submission = not project.enable_automatic_post_submission
    project.save(update_fields=["enable_automatic_post_submission"])

    return {"status": "success", "enabled": project.enable_automatic_post_submission}


@api.post("/update-title-score/{suggestion_id}", response={200: dict}, auth=[session_auth])
def update_title_score(request: HttpRequest, suggestion_id: int, data: UpdateTitleScoreIn):
    profile = request.auth
    suggestion = get_object_or_404(
        BlogPostTitleSuggestion, id=suggestion_id, project__profile=profile
    )

    if data.score not in [-1, 0, 1]:
        return {"status": "error", "message": "Invalid score value. Must be -1, 0, or 1"}

    try:
        suggestion.user_score = data.score
        suggestion.save(update_fields=["user_score"])

        return {"status": "success", "message": "Score updated successfully"}

    except Exception as e:
        logger.error(
            "Failed to update title score",
            error=str(e),
            suggestion_id=suggestion_id,
            profile_id=profile.id,
        )
        return {"status": "error", "message": f"Failed to update score: {str(e)}"}


@api.post("/suggestions/{suggestion_id}/archive-status", response={200: dict}, auth=[session_auth])
def update_archive_status(request: HttpRequest, suggestion_id: int, data: UpdateArchiveStatusIn):
    profile = request.auth
    suggestion = get_object_or_404(
        BlogPostTitleSuggestion, id=suggestion_id, project__profile=profile
    )

    try:
        suggestion.archived = data.archived
        suggestion.save(update_fields=["archived"])
        return {"status": "success"}
    except Exception as e:
        logger.error(
            "Failed to update suggestion archive status",
            error=str(e),
            suggestion_id=suggestion_id,
            profile_id=profile.id,
        )
        return {"status": "error", "message": str(e)}


@api.post("/add-pricing-page", auth=[session_auth])
def add_pricing_page(request: HttpRequest, data: AddPricingPageIn):
    profile = request.auth
    project = Project.objects.get(id=data.project_id, profile=profile)

    project_page = ProjectPage.objects.create(
        project=project, url=data.url, type=ProjectPageType.PRICING
    )

    project_page.get_page_content()
    project_page.analyze_content()

    return {"status": "success", "message": "Pricing page added successfully"}


@api.post("/add-competitor", response=CompetitorAnalysisOut, auth=[session_auth])
def add_competitor(request: HttpRequest, data: AddCompetitorIn):
    profile = request.auth
    project = get_object_or_404(Project, id=data.project_id, profile=profile)

    try:
        if Competitor.objects.filter(project=project, url=data.url).exists():
            return {"status": "error", "message": "This competitor already exists for your project"}

        competitor = Competitor.objects.create(
            project=project,
            name=data.name if hasattr(data, "name") and data.name else "Unknown Competitor",
            url=data.url,
            description=data.description
            if hasattr(data, "description") and data.description
            else "",
        )

        got_content = competitor.get_page_content()
        got_name_and_description = competitor.populate_name_description()

        if not got_content or not got_name_and_description:
            competitor.delete()
            return {
                "status": "error",
                "message": "Failed to get page content for this competitor URL",
            }

        analyzed = competitor.analyze_competitor()

        if not analyzed:
            competitor.delete()
            return {"status": "error", "message": "Failed to analyze this competitor"}

        return {
            "status": "success",
            "competitor_id": competitor.id,
            "name": competitor.name,
            "url": competitor.url,
            "description": competitor.description,
            "summary": competitor.summary,
            "competitor_analysis": competitor.competitor_analysis,
            "key_differences": competitor.key_differences,
            "strengths": competitor.strengths,
            "weaknesses": competitor.weaknesses,
            "opportunities": competitor.opportunities,
            "threats": competitor.threats,
            "key_features": competitor.key_features,
            "key_benefits": competitor.key_benefits,
            "key_drawbacks": competitor.key_drawbacks,
        }

    except Exception as e:
        logger.error(
            "Failed to add competitor",
            error=str(e),
            exc_info=True,
            project_id=project.id,
            url=data.url,
        )
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}


@api.post("/submit-feedback", auth=[session_auth])
def submit_feedback(request: HttpRequest, data: SubmitFeedbackIn):
    profile = request.auth
    Feedback.objects.create(profile=profile, feedback=data.feedback, page=data.page)
    return {"status": "success"}


@api.get("/user/settings", response=UserSettingsOut, auth=[session_auth])
def user_settings(request: HttpRequest, project_id: int):
    profile = request.auth
    try:
        project = get_object_or_404(Project, id=project_id, profile=profile)

        profile_data = {
            "has_pro_subscription": profile.has_active_subscription,
            "reached_content_generation_limit": profile.reached_content_generation_limit,
            "reached_title_generation_limit": profile.reached_title_generation_limit,
        }
        project_data = {
            "name": project.name,
            "url": project.url,
            "has_auto_submission_setting": project.has_auto_submission_setting,
        }
        data = {"profile": profile_data, "project": project_data}

        return data
    except Exception as e:
        logger.error(
            "Error fetching user settings",
            error=str(e),
            project_id=project_id,
            profile_id=profile.id,
            exc_info=True,
        )
        raise


@api.post("/keywords/add", response=AddKeywordOut, auth=[session_auth])
def add_keyword_to_project(request: HttpRequest, data: AddKeywordIn):
    profile = request.auth
    project = get_object_or_404(Project, id=data.project_id, profile=profile)

    keyword_text_cleaned = data.keyword_text.strip().lower()
    if not keyword_text_cleaned:
        return {"status": "error", "message": "Keyword text cannot be empty."}

    try:
        keyword, created = Keyword.objects.get_or_create(
            keyword_text=keyword_text_cleaned,
        )

        project_keyword, pk_created = ProjectKeyword.objects.get_or_create(
            project=project, keyword=keyword
        )

        if created:
            metrics_fetched = keyword.fetch_and_update_metrics()
            if not metrics_fetched:
                logger.warning(
                    "[AddKeyword] Failed to fetch metrics for keyword.",
                    keyword_id=keyword.id,
                    project_id=project.id,
                )
                return {
                    "status": "error",
                    "message": "Keyword added, but metrics fetch failed/pending.",
                }

        keyword_data = {
            "id": keyword.id,
            "keyword_text": keyword.keyword_text,
            "volume": keyword.volume,
            "cpc_currency": keyword.cpc_currency,
            "cpc_value": float(keyword.cpc_value) if keyword.cpc_value is not None else None,
            "competition": keyword.competition,
            "country": keyword.country,
            "data_source": keyword.data_source,
            "last_fetched_at": keyword.last_fetched_at.isoformat()
            if keyword.last_fetched_at
            else None,
            "trend_data": [
                {"value": trend.value, "month": trend.month, "year": trend.year}
                for trend in keyword.trends.all()
            ],
        }

        return {
            "status": "success",
            "message": "Keyword added",
            "keyword": keyword_data,
        }

    except Exception as e:
        logger.error(
            "[AddKeyword] Failed to add keyword to project",
            error=str(e),
            exc_info=True,
            project_id=project.id,
            keyword_text=data.keyword_text,
        )
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}


@api.post("/keywords/toggle-use", response=ToggleProjectKeywordUseOut, auth=[session_auth])
def toggle_project_keyword_use(request: HttpRequest, data: ToggleProjectKeywordUseIn):
    profile = request.auth
    try:
        project = get_object_or_404(Project, id=data.project_id, profile=profile)
        project_keyword = get_object_or_404(
            ProjectKeyword, project=project, keyword_id=data.keyword_id
        )
        project_keyword.use = not project_keyword.use
        project_keyword.save(update_fields=["use"])
        return ToggleProjectKeywordUseOut(status="success", use=project_keyword.use)
    except Exception as e:
        logger.error(
            "Failed to toggle ProjectKeyword use field",
            error=str(e),
            project_id=data.project_id,
            keyword_id=data.keyword_id,
            profile_id=profile.id,
        )
        return ToggleProjectKeywordUseOut(status="error", message=f"Failed to toggle use: {str(e)}")


@api.post("/keywords/delete", response=DeleteProjectKeywordOut, auth=[session_auth])
def delete_project_keyword(request: HttpRequest, data: DeleteProjectKeywordIn):
    profile = request.auth
    try:
        project = get_object_or_404(Project, id=data.project_id, profile=profile)
        project_keyword = get_object_or_404(
            ProjectKeyword, project=project, keyword_id=data.keyword_id
        )
        keyword_text = project_keyword.keyword.keyword_text
        project_keyword.delete()
        return DeleteProjectKeywordOut(
            status="success", message=f"Keyword '{keyword_text}' removed from project"
        )
    except Exception as e:
        logger.error(
            "Failed to delete ProjectKeyword",
            error=str(e),
            project_id=data.project_id,
            keyword_id=data.keyword_id,
            profile_id=profile.id,
        )
        return DeleteProjectKeywordOut(
            status="error", message=f"Failed to delete keyword: {str(e)}"
        )


@api.post("/blog-posts/submit", response=BlogPostOut, auth=[superuser_api_auth])
def submit_blog_post(request: HttpRequest, data: BlogPostIn):
    try:
        BlogPost.objects.create(
            title=data.title,
            description=data.description,
            slug=data.slug,
            tags=data.tags,
            content=data.content,
            status=data.status,
            # icon and image are ignored for now (file upload not handled)
        )
        return BlogPostOut(status="success", message="Blog post submitted successfully.")
    except Exception as e:
        return BlogPostOut(status="error", message=f"Failed to submit blog post: {str(e)}")


@api.post("/post-generated-blog-post", response=PostGeneratedBlogPostOut, auth=[session_auth])
def post_generated_blog_post(request: HttpRequest, data: PostGeneratedBlogPostIn):
    profile = request.auth

    blog_post_id = data.id
    if not blog_post_id:
        return {"status": "error", "message": "Missing generated blog post id."}
    try:
        generated_post = GeneratedBlogPost.objects.get(id=blog_post_id)
        if generated_post.project and generated_post.project.profile != profile:
            return {"status": "error", "message": "Forbidden: You do not have access to this post."}
        result = generated_post.submit_blog_post_to_endpoint()
        if result is True:
            generated_post.posted = True
            generated_post.date_posted = timezone.now()
            generated_post.save(update_fields=["posted", "date_posted"])
            return {"status": "success", "message": "Blog post published!"}
        else:
            return {"status": "error", "message": "Failed to post blog."}
    except GeneratedBlogPost.DoesNotExist:
        return {"status": "error", "message": "Generated blog post not found."}
    except Exception as e:
        logger.error("Failed to post generated blog post", error=str(e), blog_post_id=blog_post_id)
        return {"status": "error", "message": str(e)}
