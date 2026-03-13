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
    blog_theme: str = ""
    founders: str = ""
    key_features: str = ""
    target_audience_summary: str = ""
    pain_points: str = ""
    product_usage: str = ""
    links: str = ""
    language: str = ""
    location: str = ""


class PublicProjectCreateOut(Schema):
    status: str
    message: str = ""
    project: PublicProjectOut | None = None


class PublicProjectGetOut(Schema):
    status: str
    message: str = ""
    project: PublicProjectOut | None = None


class PublicProjectUpdateIn(Schema):
    name: str | None = None
    summary: str | None = None
    blog_theme: str | None = None
    founders: str | None = None
    key_features: str | None = None
    target_audience_summary: str | None = None
    pain_points: str | None = None
    product_usage: str | None = None
    links: str | None = None
    language: str | None = None
    location: str | None = None


class PublicProjectUpdateOut(Schema):
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


class PublicTitleSuggestionOut(Schema):
    id: int
    title: str
    category: str = ""
    description: str = ""
    target_keywords: list[str] = []
    suggested_meta_description: str = ""
    content_type: str
    status: str


class PublicPaginationOut(Schema):
    page: int
    page_size: int
    total: int


class PublicTitleSuggestionListOut(Schema):
    status: str
    suggestions: list[PublicTitleSuggestionOut] = []
    pagination: PublicPaginationOut


class PublicTitleSuggestionGetOut(Schema):
    status: str
    suggestion: PublicTitleSuggestionOut | None = None


class PublicTitleSuggestionCreateIn(Schema):
    count: int = Field(default=3, gt=0)
    content_type: str = "SHARING"
    seed_guidance: str = ""


class PublicTitleSuggestionCreateOut(Schema):
    status: str
    count: int
    suggestions: list[PublicTitleSuggestionOut] = []
