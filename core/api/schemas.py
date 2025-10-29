from ninja import Schema

from core.choices import BlogPostStatus, ContentType


class ProfileSettingsOut(Schema):
    has_pro_subscription: bool
    reached_content_generation_limit: bool
    reached_title_generation_limit: bool


class ProjectSettingsOut(Schema):
    name: str
    url: str
    has_auto_submission_setting: bool


class UserSettingsOut(Schema):
    profile: ProfileSettingsOut
    project: ProjectSettingsOut


class ProjectScanIn(Schema):
    url: str
    source: str = "default"


class ValidateUrlIn(Schema):
    url: str


class ValidateUrlOut(Schema):
    status: str
    reachable: bool
    message: str = ""


class ProjectScanOut(Schema):
    status: str
    message: str = ""
    project_id: int = 0
    name: str = ""
    type: str = ""
    url: str = ""
    summary: str = ""


class GenerateTitleSuggestionsIn(Schema):
    project_id: int
    content_type: str = ContentType.SHARING
    user_prompt: str = ""
    num_titles: int = 3


class TitleSuggestionOut(Schema):
    id: int
    title: str
    category: str = ""
    description: str = ""
    target_keywords: list[str] = []
    suggested_meta_description: str = ""


class GenerateTitleSuggestionOut(Schema):
    status: str
    message: str = ""
    suggestion: TitleSuggestionOut = {}
    suggestion_html: str = ""  # Rendered HTML for the suggestion


class GenerateTitleSuggestionsOut(Schema):
    suggestions: list[TitleSuggestionOut] = []
    suggestions_html: list[str] = []  # Rendered HTML for each suggestion
    status: str
    message: str = ""


class GeneratedContentOut(Schema):
    status: str = "success"
    message: str | None = None
    content: str | None = None
    slug: str | None = None
    tags: str | None = None
    description: str | None = None
    id: int | None = None


class UpdateTitleScoreIn(Schema):
    score: int


class UpdateArchiveStatusIn(Schema):
    archived: bool


class AddPricingPageIn(Schema):
    project_id: int
    url: str


class CreatePricingStrategyIn(Schema):
    project_id: int
    strategy_name: str = "Alex Hormozi"
    user_prompt: str = ""


class AddCompetitorIn(Schema):
    project_id: int
    url: str
    name: str | None = None
    description: str | None = None


class CompetitorAnalysisOut(Schema):
    status: str
    message: str | None = None
    competitor_id: int | None = None
    name: str | None = None
    url: str | None = None
    description: str | None = None
    summary: str | None = None
    competitor_analysis: str | None = None
    key_differences: str | None = None
    strengths: str | None = None
    weaknesses: str | None = None
    opportunities: str | None = None
    threats: str | None = None
    key_features: str | None = None
    key_benefits: str | None = None
    key_drawbacks: str | None = None


class SubmitFeedbackIn(Schema):
    feedback: str
    page: str


class AddKeywordIn(Schema):
    project_id: int
    keyword_text: str


class KeywordMetricsOut(Schema):
    id: int
    keyword_text: str
    volume: int | None = None
    cpc_currency: str | None = None
    cpc_value: float | None = None  # Using float for schema, Decimal in model
    competition: float | None = None
    country: str | None = None
    data_source: str | None = None
    last_fetched_at: str | None = None  # datetime converted to str
    trend_data: list[dict] | None = None
    is_in_project: bool | None = None
    in_use: bool | None = None
    project_keyword_id: int | None = None


class AddKeywordOut(Schema):
    status: str
    message: str | None = None
    keyword: KeywordMetricsOut | None = None


class ToggleProjectKeywordUseIn(Schema):
    project_id: int
    keyword_id: int


class ToggleProjectKeywordUseOut(Schema):
    status: str
    message: str | None = None
    use: bool | None = None


class DeleteProjectKeywordIn(Schema):
    project_id: int
    keyword_id: int


class DeleteProjectKeywordOut(Schema):
    status: str
    message: str | None = None


class BlogPostIn(Schema):
    title: str
    description: str = ""
    slug: str
    tags: str = ""
    content: str
    icon: str | None = None  # URL or base64 string
    image: str | None = None  # URL or base64 string
    status: BlogPostStatus = BlogPostStatus.DRAFT


class BlogPostOut(Schema):
    status: str
    message: str


class PostGeneratedBlogPostIn(Schema):
    id: int


class PostGeneratedBlogPostOut(Schema):
    status: str
    message: str


class ToggleAutoSubmissionOut(Schema):
    status: str
    enabled: bool
    message: str = ""


class FixGeneratedBlogPostIn(Schema):
    id: int


class FixGeneratedBlogPostOut(Schema):
    status: str
    message: str


class GetKeywordDetailsOut(Schema):
    status: str
    message: str | None = None
    keyword: KeywordMetricsOut | None = None
