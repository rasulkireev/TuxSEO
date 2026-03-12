from ninja import Schema
from pydantic import Field


class PublicAPIErrorOut(Schema):
    status: str = "error"
    message: str


class PublicAccountOut(Schema):
    account_id: int
    email: str
    product_name: str
    is_on_pro_plan: bool
    project_limit: int | None = None
    active_project_count: int


class PublicProjectIn(Schema):
    url: str
    source: str = "public_api"


class PublicProjectOut(Schema):
    project_id: int
    name: str
    type: str
    url: str
    summary: str


class PublicProjectCreateOut(Schema):
    status: str
    message: str = ""
    project: PublicProjectOut | None = None


class PublicContentAutomationIn(Schema):
    endpoint_url: str
    request_body_json: dict = Field(default_factory=dict)
    request_headers_json: dict = Field(default_factory=dict)
    posts_per_month: int = Field(default=1, gt=0)
    enable_automatic_post_submission: bool = True


class PublicContentAutomationOut(Schema):
    status: str
    message: str
    project_id: int
    content_automation_id: int
    enable_automatic_post_submission: bool
