from django.http import HttpRequest
from ninja import NinjaAPI

from core.abuse_prevention import enforce_verified_email_for_expensive_action
from core.models import AutoSubmissionSetting, Project
from core.public_api.auth import public_api_key_auth
from core.public_api.schemas import (
    PublicAccountOut,
    PublicContentAutomationIn,
    PublicContentAutomationOut,
    PublicAPIErrorOut,
    PublicProjectCreateOut,
    PublicProjectIn,
)
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)

public_api = NinjaAPI(
    title="TuxSEO Public API",
    version="1.0.0",
    urls_namespace="public_api",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


def get_verified_email_gate_error(profile, action_name: str) -> dict | None:
    return enforce_verified_email_for_expensive_action(profile=profile, action_name=action_name)


@public_api.get("/account", response=PublicAccountOut, auth=[public_api_key_auth])
def get_public_account(request: HttpRequest):
    profile = request.auth

    return {
        "account_id": profile.id,
        "email": profile.user.email,
        "product_name": profile.product_name,
        "is_on_pro_plan": profile.is_on_pro_plan,
        "project_limit": profile.project_limit,
        "active_project_count": profile.number_of_active_projects,
    }


@public_api.post(
    "/projects",
    response={200: PublicProjectCreateOut, 400: PublicAPIErrorOut, 500: PublicAPIErrorOut},
    auth=[public_api_key_auth],
)
def create_public_project(request: HttpRequest, data: PublicProjectIn):
    profile = request.auth

    gate_error = get_verified_email_gate_error(profile, "project creation")
    if gate_error:
        return 400, {"message": gate_error["message"]}

    project_url = data.url.strip()
    if not project_url:
        return 400, {"message": "Project URL cannot be empty"}

    if not project_url.startswith(("http://", "https://")):
        return 400, {"message": "Project URL must start with http:// or https://"}

    if Project.objects.filter(profile=profile, url=project_url).exists():
        return 400, {"message": "You already added this project URL"}

    if not profile.can_create_project:
        if profile.is_on_free_plan:
            limit = profile.project_limit
            limit_message = (
                f"Project creation limit reached ({limit} project on Free plan). "
                "Upgrade to Pro to create more projects."
            )
            return 400, {"message": limit_message}

        return 400, {"message": "Project creation limit reached. Contact support for assistance."}

    project = profile.get_or_create_project(url=project_url, source=data.source)

    try:
        got_project_content = project.get_page_content()
        if not got_project_content:
            project.delete()
            return 400, {"message": "Failed to get page content"}

        is_project_analyzed = project.analyze_content()
        if not is_project_analyzed:
            project.delete()
            return 400, {"message": "Failed to analyze project"}

        return {
            "status": "success",
            "project": {
                "project_id": project.id,
                "name": project.name,
                "type": project.get_type_display(),
                "url": project.url,
                "summary": project.summary,
            },
        }
    except Exception as error:
        logger.error(
            "[Public API] Unexpected error during project creation",
            error=str(error),
            exc_info=True,
            profile_id=profile.id,
            url=project_url,
        )
        if project.id:
            project.delete()
        return 500, {"message": "An unexpected error occurred while creating the project"}


@public_api.post(
    "/projects/{project_id}/content-automation",
    response={
        200: PublicContentAutomationOut,
        400: PublicAPIErrorOut,
        404: PublicAPIErrorOut,
        500: PublicAPIErrorOut,
    },
    auth=[public_api_key_auth],
)
def configure_content_automation(
    request: HttpRequest, project_id: int, data: PublicContentAutomationIn
):
    profile = request.auth

    project = Project.objects.filter(id=project_id, profile=profile).first()
    if project is None:
        return 404, {"message": "Project not found"}

    if not profile.is_on_pro_plan:
        return 400, {
            "message": "Automatic Post Submission is only available on the Pro plan."
        }

    endpoint_url = data.endpoint_url.strip()
    if not endpoint_url:
        return 400, {"message": "Endpoint URL cannot be empty"}

    if not endpoint_url.startswith(("http://", "https://")):
        return 400, {"message": "Endpoint URL must start with http:// or https://"}

    try:
        content_automation, _ = AutoSubmissionSetting.objects.update_or_create(
            project=project,
            defaults={
                "endpoint_url": endpoint_url,
                "body": data.request_body_json,
                "header": data.request_headers_json,
                "posts_per_month": data.posts_per_month,
            },
        )

        project.enable_automatic_post_submission = data.enable_automatic_post_submission
        project.save(update_fields=["enable_automatic_post_submission"])

        return {
            "status": "success",
            "message": "Content automation settings saved",
            "project_id": project.id,
            "content_automation_id": content_automation.id,
            "enable_automatic_post_submission": project.enable_automatic_post_submission,
        }
    except Exception as error:
        logger.error(
            "[Public API] Failed to configure content automation",
            error=str(error),
            exc_info=True,
            project_id=project_id,
            profile_id=profile.id,
        )
        return 500, {"message": "Failed to save content automation settings"}
