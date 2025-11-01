from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django_q.tasks import async_task
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from core.agents import content_editor_agent
from core.base_models import BaseModel
from core.choices import (
    BlogPostStatus,
    Category,
    ContentType,
    KeywordDataSource,
    Language,
    ProfileStates,
    ProjectPageSource,
    ProjectPageType,
    ProjectStyle,
    ProjectType,
)
from core.model_utils import (
    generate_random_key,
    get_markdown_content,
    run_agent_synchronously,
)
from core.prompts import (
    GENERATE_CONTENT_SYSTEM_PROMPTS,
    TITLE_SUGGESTION_SYSTEM_PROMPTS,
)
from core.schemas import (
    BlogPostGenerationContext,
    CompetitorAnalysis,
    CompetitorAnalysisContext,
    CompetitorDetails,
    GeneratedBlogPostSchema,
    ProjectDetails,
    ProjectPageContext,
    TitleSuggestion,
    TitleSuggestionContext,
    TitleSuggestions,
    WebPageContent,
)
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


class Profile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    key = models.CharField(max_length=10, unique=True, default=generate_random_key)
    experimental_features = models.BooleanField(default=False)

    subscription = models.ForeignKey(
        "djstripe.Subscription",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="profile",
        help_text="The user's Stripe Subscription object, if it exists",
    )
    product = models.ForeignKey(
        "djstripe.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="profile",
        help_text="The user's Stripe Product object, if it exists",
    )
    customer = models.ForeignKey(
        "djstripe.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="profile",
        help_text="The user's Stripe Customer object, if it exists",
    )

    state = models.CharField(
        max_length=255,
        choices=ProfileStates.choices,
        default=ProfileStates.STRANGER,
        help_text="The current state of the user's profile",
    )

    def __str__(self):
        return f"{self.user.username}"

    def track_state_change(self, to_state, metadata=None):
        async_task(
            "core.tasks.track_state_change",
            profile_id=self.id,
            from_state=self.current_state,
            to_state=to_state,
            metadata=metadata,
            source_function="Profile - track_state_change",
            group="Track State Change",
        )

    @property
    def current_state(self):
        if not self.state_transitions.all().exists():
            return ProfileStates.STRANGER
        latest_transition = self.state_transitions.latest("created_at")
        return latest_transition.to_state

    @property
    def has_product_or_subscription(self):
        return self.user.is_superuser or self.product is not None or self.subscription is not None

    @property
    def number_of_active_projects(self):
        return self.projects.count()

    @property
    def number_of_generated_blog_posts(self):
        projects = self.projects.all()
        return sum(project.generated_blog_posts.count() for project in projects)

    @property
    def number_of_generated_blog_posts_this_month(self):
        now = timezone.now()
        first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        projects = self.projects.all()
        blog_post_count = 0
        for project in projects:
            blog_post_count += project.generated_blog_posts.filter(
                created_at__gte=first_day_of_month
            ).count()
        return blog_post_count

    @property
    def number_of_title_suggestions(self):
        projects = self.projects.all()
        return sum(project.blog_post_title_suggestions.count() for project in projects)

    @property
    def number_of_title_suggestions_this_month(self):
        now = timezone.now()
        first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        projects = self.projects.all()
        suggestion_count = 0
        for project in projects:
            suggestion_count += project.blog_post_title_suggestions.filter(
                created_at__gte=first_day_of_month
            ).count()
        return suggestion_count

    @property
    def product_name(self):
        if self.user.is_superuser:
            return "Pro"
        if self.product and hasattr(self.product, "name"):
            return self.product.name
        return "Free"

    @property
    def is_on_free_plan(self):
        return self.product_name == "Free"

    @property
    def is_on_pro_plan(self):
        if self.user.is_superuser:
            return True
        product_name_lower = self.product_name.lower()
        return "pro" in product_name_lower

    @property
    def project_limit(self):
        if self.is_on_pro_plan:
            return None
        return 1

    @property
    def title_suggestion_limit(self):
        if self.is_on_free_plan:
            return 10
        return None

    @property
    def blog_post_generation_limit(self):
        if self.is_on_free_plan:
            return 3
        return None

    @property
    def has_auto_posting_enabled(self):
        return not self.is_on_free_plan

    @property
    def keyword_limit_per_month(self):
        if self.is_on_free_plan:
            return 0
        return None

    @property
    def number_of_keywords_added_this_month(self):
        now = timezone.now()
        first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        projects = self.projects.all()
        keyword_count = 0
        for project in projects:
            keyword_count += project.project_keywords.filter(
                date_associated__gte=first_day_of_month
            ).count()
        return keyword_count

    @property
    def reached_keyword_limit(self):
        limit = self.keyword_limit_per_month
        if limit is None:
            return False
        return self.number_of_keywords_added_this_month >= limit

    @property
    def can_add_keywords(self):
        return not self.reached_keyword_limit

    @property
    def reached_project_creation_limit(self):
        limit = self.project_limit
        if limit is None:
            return False
        return self.number_of_active_projects >= limit

    @property
    def reached_title_generation_limit(self):
        limit = self.title_suggestion_limit
        if limit is None:
            return False
        return self.number_of_title_suggestions_this_month >= limit

    @property
    def reached_content_generation_limit(self):
        limit = self.blog_post_generation_limit
        if limit is None:
            return False
        return self.number_of_generated_blog_posts_this_month >= limit

    @property
    def can_create_project(self):
        return not self.reached_project_creation_limit

    @property
    def can_generate_title_suggestions(self):
        return not self.reached_title_generation_limit

    @property
    def can_generate_blog_posts(self):
        return not self.reached_content_generation_limit


class ProfileStateTransition(BaseModel):
    profile = models.ForeignKey(
        Profile, null=True, blank=True, on_delete=models.SET_NULL, related_name="state_transitions"
    )
    from_state = models.CharField(max_length=255, choices=ProfileStates.choices)
    to_state = models.CharField(max_length=255, choices=ProfileStates.choices)
    backup_profile_id = models.IntegerField()
    metadata = models.JSONField(null=True, blank=True)


class BlogPost(BaseModel):
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=250)
    tags = models.TextField()
    content = models.TextField()
    icon = models.ImageField(upload_to="blog_post_icons/", blank=True)
    image = models.ImageField(upload_to="blog_post_images/", blank=True)

    status = models.CharField(
        max_length=20,
        choices=BlogPostStatus.choices,
        default=BlogPostStatus.DRAFT,
    )

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog_post", kwargs={"slug": self.slug})


class Project(BaseModel):
    profile = models.ForeignKey(
        Profile, null=True, blank=True, on_delete=models.CASCADE, related_name="projects"
    )
    url = models.URLField(max_length=200, unique=True)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50, choices=ProjectType.choices, default=ProjectType.SAAS)
    summary = models.TextField(blank=True)

    # Agent Settings
    enable_automatic_post_submission = models.BooleanField(default=False)
    enable_automatic_post_generation = models.BooleanField(default=True)

    # Sitemap
    sitemap_url = models.URLField(max_length=500, blank=True, default="")

    # Content from Jina Reader
    date_scraped = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=500, blank=True, default="")
    description = models.TextField(blank=True, default="")
    markdown_content = models.TextField(blank=True, default="")

    # AI Content
    date_analyzed = models.DateTimeField(null=True, blank=True)
    blog_theme = models.TextField(blank=True)
    founders = models.TextField(blank=True)
    key_features = models.TextField(blank=True)
    language = models.CharField(max_length=50, choices=Language.choices, default=Language.ENGLISH)
    target_audience_summary = models.TextField(blank=True)
    pain_points = models.TextField(blank=True)
    product_usage = models.TextField(blank=True)
    links = models.TextField(blank=True)
    competitors_list = models.TextField(blank=True)
    style = models.CharField(
        max_length=50, choices=ProjectStyle.choices, default=ProjectStyle.DIGITAL_ART
    )
    proposed_keywords = models.TextField(blank=True)
    location = models.CharField(max_length=50, default="Global")

    def __str__(self):
        return self.name

    @property
    def project_details(self):
        return ProjectDetails(
            name=self.name,
            type=self.type,
            summary=self.summary,
            blog_theme=self.blog_theme,
            founders=self.founders,
            key_features=self.key_features,
            target_audience_summary=self.target_audience_summary,
            pain_points=self.pain_points,
            product_usage=self.product_usage,
            links=self.links,
            language=self.language,
            proposed_keywords=self.proposed_keywords,
            location=self.location,
        )

    @property
    def title_suggestions(self):
        return self.blog_post_title_suggestions.all()

    @property
    def liked_title_suggestions(self):
        return self.blog_post_title_suggestions.filter(user_score__gt=0).all()

    @property
    def disliked_title_suggestions(self):
        return self.blog_post_title_suggestions.filter(user_score__lt=0).all()

    @property
    def neutral_title_suggestions(self):
        return self.blog_post_title_suggestions.filter(user_score=0).all()

    @property
    def generated_blog_posts(self):
        return self.generated_blog_posts.all()

    @property
    def last_posted_blog_post(self):
        generated_blog_posts = self.generated_blog_posts
        if generated_blog_posts.exists():
            return (
                generated_blog_posts.filter(posted=True, date_posted__isnull=False)
                .order_by("-date_posted")
                .first()
            )
        return None

    @property
    def has_auto_submission_setting(self):
        return self.auto_submission_settings.exists()

    def get_page_content(self):
        """
        Fetch page content using Jina Reader API and update the project.
        Returns the content if successful, raises ValueError otherwise.
        """
        title, description, markdown_content = get_markdown_content(self.url)

        if not markdown_content:
            logger.error(
                "[Get Page Content] Failed to get page content",
                url=self.url,
            )
            return False

        self.date_scraped = timezone.now()
        self.title = title
        self.description = description
        self.markdown_content = markdown_content

        self.save(
            update_fields=[
                "date_scraped",
                "title",
                "description",
                "markdown_content",
            ]
        )

        return True

    def analyze_content(self):
        """
        Analyze the page content using PydanticAI and update project details.
        Should be called after get_page_content().
        """
        from core.agents import analyze_project_agent

        result = run_agent_synchronously(
            analyze_project_agent,
            "Analyze this web page content and extract the key information.",
            deps=WebPageContent(
                title=self.title,
                description=self.description,
                markdown_content=self.markdown_content,
            ),
            function_name="analyze_content",
            model_name="Project",
        )

        self.name = result.data.name
        self.type = result.data.type
        self.summary = result.data.summary
        self.blog_theme = result.data.blog_theme
        self.founders = result.data.founders
        self.key_features = result.data.key_features
        self.target_audience_summary = result.data.target_audience_summary
        self.pain_points = result.data.pain_points
        self.product_usage = result.data.product_usage
        self.links = result.data.links
        self.language = result.data.language
        self.proposed_keywords = result.data.proposed_keywords
        self.location = result.data.location
        self.date_analyzed = timezone.now()
        self.save()

        async_task("core.tasks.generate_blog_post_suggestions", self.id)
        async_task("core.tasks.process_project_keywords", self.id)
        async_task("core.tasks.schedule_project_page_analysis", self.id)
        async_task("core.tasks.schedule_project_competitor_analysis", self.id, timeout=180)

        return True

    def generate_title_suggestions(  # noqa: C901
        self, content_type=ContentType.SHARING, num_titles=3, user_prompt=""
    ):
        agent = Agent(
            "google-gla:gemini-2.5-flash",
            output_type=TitleSuggestions,
            deps_type=TitleSuggestionContext,
            system_prompt=TITLE_SUGGESTION_SYSTEM_PROMPTS[content_type],
            retries=2,
            model_settings={"temperature": 0.9},
        )

        @agent.system_prompt
        def add_todays_date() -> str:
            return f"Today's Date: {timezone.now().strftime('%Y-%m-%d')}"

        @agent.system_prompt
        def add_project_details(ctx: RunContext[TitleSuggestionContext]) -> str:
            project = ctx.deps.project_details
            return f"""
                Project Details:
                - Project Name: {project.name}
                - Project Type: {project.type}
                - Project Summary: {project.summary}
                - Blog Theme: {project.blog_theme}
                - Founders: {project.founders}
                - Key Features: {project.key_features}
                - Target Audience: {project.target_audience_summary}
                - Pain Points: {project.pain_points}
                - Product Usage: {project.product_usage}
            """

        @agent.system_prompt
        def add_number_of_titles_to_generate(ctx: RunContext[TitleSuggestionContext]) -> str:
            return f"""IMPORTANT: Generate only {ctx.deps.num_titles} titles."""

        @agent.system_prompt
        def add_language_specification(ctx: RunContext[TitleSuggestionContext]) -> str:
            project = ctx.deps.project_details
            return f"""
                IMPORTANT: Generate all titles in {project.language} language.
                Make sure the titles are grammatically correct and culturally
                appropriate for {project.language}-speaking audiences.
            """

        @agent.system_prompt
        def add_user_prompt(ctx: RunContext[TitleSuggestionContext]) -> str:
            if not ctx.deps.user_prompt:
                return ""

            return f"""
                IMPORTANT USER REQUEST: The user has specifically requested the following:
                "{ctx.deps.user_prompt}"

                This is a high-priority requirement. Make sure to incorporate this guidance
                when generating titles while still maintaining SEO best practices and readability.
            """

        @agent.system_prompt
        def add_feedback_history(ctx: RunContext[TitleSuggestionContext]) -> str:
            # Build the feedback sections only if they exist
            feedback_sections = []

            if ctx.deps.neutral_suggestions:
                neutral = "\n".join(f"- {title}" for title in ctx.deps.neutral_suggestions)
                feedback_sections.append(
                    f"""
                    Title Suggestions that users have not yet liked or disliked:
                    {neutral}
                """
                )

            if ctx.deps.liked_suggestions:
                liked = "\n".join(f"- {title}" for title in ctx.deps.liked_suggestions)
                feedback_sections.append(
                    f"""
                    Liked Title Suggestions:
                    {liked}
                """
                )

            if ctx.deps.disliked_suggestions:
                disliked = "\n".join(f"- {title}" for title in ctx.deps.disliked_suggestions)
                feedback_sections.append(
                    f"""
                    Disliked Title Suggestions:
                    {disliked}
                """
                )

            # Add guidance only if we have any feedback
            if feedback_sections:
                feedback_sections.append(
                    """
                    Use this feedback to guide your title generation.
                    Create titles that are thematically similar to the "Liked" titles,
                    and avoid any stylistic or thematic patterns from the "Disliked" titles.

                    IMPORTANT!
                    You must generate completely new and unique titles.
                    Do not repeat or create minor variations of any titles listed above in the
                    "Previously Generated", "Liked", or "Disliked" sections.
                    Your primary goal is originality.
                    """
                )

            return "\n".join(feedback_sections)

        deps = TitleSuggestionContext(
            project_details=self.project_details,
            num_titles=num_titles,
            user_prompt=user_prompt,
            liked_suggestions=[suggestion.title for suggestion in self.liked_title_suggestions],
            disliked_suggestions=[
                suggestion.title for suggestion in self.disliked_title_suggestions
            ],
            neutral_suggestions=[suggestion.title for suggestion in self.neutral_title_suggestions],
        )

        result = run_agent_synchronously(
            agent,
            "Please generate blog post title suggestions based on the project details.",
            deps=deps,
            function_name="generate_title_suggestions",
            model_name="Project",
        )

        with transaction.atomic():
            suggestions = []
            for title in result.data.titles:
                suggestion = BlogPostTitleSuggestion(
                    project=self,
                    title=title.title,
                    description=title.description,
                    category=title.category,
                    content_type=content_type,
                    target_keywords=title.target_keywords,
                    prompt=user_prompt,
                    suggested_meta_description=title.suggested_meta_description,
                )
                suggestions.append(suggestion)

            created_suggestions = BlogPostTitleSuggestion.objects.bulk_create(suggestions)

            # Schedule background tasks to save target keywords for each suggestion
            for suggestion in created_suggestions:
                if suggestion.target_keywords:
                    async_task("core.tasks.save_title_suggestion_keywords", suggestion.id)

            return created_suggestions

    def get_a_list_of_links(self):
        agent = Agent(
            "google-gla:gemini-2.5-flash",
            output_type=list[str],
            deps_type=str,
            system_prompt="""
                You are an expert link extractor.
                Extract all the URLs from the markdown-formatted text provided.
                Return only valid, complete URLs (starting with http:// or https://).
                If the text contains no valid URLs, return an empty list.
            """,
            retries=2,
        )

        @agent.system_prompt
        def add_links_text(ctx: RunContext[str]) -> str:
            return f"Markdown text containing links:\n{ctx.deps}"

        result = run_agent_synchronously(
            agent,
            "Please extract all the URLs from this markdown text and return them as a list.",
            deps=self.links,
            function_name="get_a_list_of_links",
            model_name="Project",
        )

        return result.data

    def find_competitors(self):
        model = OpenAIModel(
            "sonar",
            provider=OpenAIProvider(
                base_url="https://api.perplexity.ai",
                api_key=settings.PERPLEXITY_API_KEY,
            ),
        )
        agent = Agent(
            model,
            deps_type=ProjectDetails,
            output_type=str,
            system_prompt="""
                You are a helpful assistant that helps me find competitors for my project.
            """,
            retries=2,
        )

        @agent.system_prompt
        def add_project_details(ctx: RunContext[ProjectDetails]) -> str:
            project = ctx.deps
            return f"""I'm working on a project which has the following attributes:
                Name:
                {project.name}

                Summary:
                {project.summary}

                Key Features:
                {project.key_features}

                Target Audience:
                {project.target_audience_summary}

                Pain Points Addressed:
                {project.pain_points}

                Language: {project.language}
            """

        @agent.system_prompt
        def required_data() -> str:
            return "Make sure that each competitor has a name, url, and description."

        @agent.system_prompt
        def number_of_competitors() -> str:
            return "Give me a list of at least 20 competitors."

        @agent.system_prompt
        def language_specification(ctx: RunContext[ProjectDetails]) -> str:
            project = ctx.deps
            return f"""
                IMPORTANT: Be mindful that competitors are likely to speak in
                {project.language} language.
            """

        @agent.system_prompt
        def location_specification(ctx: RunContext[ProjectDetails]) -> str:
            project = ctx.deps
            if project.location != "Global":
                return f"""
                    IMPORTANT: Only return competitors whose target audience is in
                    {project.location}.
                """
            else:
                return """
                    IMPORTANT: Return competitors from all over the world.
                """

        result = run_agent_synchronously(
            agent,
            "Give me a list of sites that might be considered my competition.",
            deps=self.project_details,
            function_name="find_competitors",
            model_name="Project",
        )

        self.competitors_list = result.data
        self.save(update_fields=["competitors_list"])

        return result.data

    def get_and_save_list_of_competitors(self):
        agent = Agent(
            "google-gla:gemini-2.5-flash",
            output_type=list[CompetitorDetails],
            system_prompt="""
                You are an expert data extractor.
                Extract all the data from the text provided.
            """,
            retries=2,
        )

        @agent.system_prompt
        def add_competitors(ctx: RunContext[list[CompetitorDetails]]) -> str:
            return f"Here are the competitors: {ctx.deps}"

        result = run_agent_synchronously(
            agent,
            "Please extract all the competitors from the text provided.",
            deps=self.competitors_list,
            function_name="get_and_save_list_of_competitors",
            model_name="Project",
        )

        competitors = []
        for competitor in result.data:
            competitors.append(
                Competitor(
                    project=self,
                    name=competitor.name,
                    url=competitor.url,
                    description=competitor.description,
                )
            )

        competitors = Competitor.objects.bulk_create(competitors)

        return competitors


class BlogPostTitleSuggestion(BaseModel):
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="blog_post_title_suggestions",
    )

    title = models.CharField(max_length=255)
    content_type = models.CharField(
        max_length=20, choices=ContentType.choices, default=ContentType.SHARING
    )
    category = models.CharField(
        max_length=50, choices=Category.choices, default=Category.GENERAL_AUDIENCE
    )
    description = models.TextField()
    prompt = models.TextField(blank=True)
    target_keywords = models.JSONField(default=list, blank=True, null=True)
    suggested_meta_description = models.TextField(blank=True)

    user_score = models.SmallIntegerField(
        default=0,
        choices=[
            (-1, "Didn't Like"),
            (0, "Undecided"),
            (1, "Liked"),
        ],
        help_text="User's rating of the title suggestion",
    )

    archived = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.project.name}: {self.title}"

    @property
    def title_suggestion_schema(self):
        return TitleSuggestion(
            title=self.title,
            category=self.category,
            target_keywords=self.target_keywords,
            description=self.description,
            suggested_meta_description=self.suggested_meta_description,
        )

    def generate_content(self, content_type=ContentType.SHARING):
        agent = Agent(
            "google-gla:gemini-2.5-flash",
            output_type=GeneratedBlogPostSchema,
            deps_type=BlogPostGenerationContext,
            system_prompt=GENERATE_CONTENT_SYSTEM_PROMPTS[content_type],
            retries=2,
            model_settings={"max_tokens": 65500, "temperature": 0.8},
        )

        @agent.system_prompt
        def add_todays_date() -> str:
            return f"Today's Date: {timezone.now().strftime('%Y-%m-%d')}"

        @agent.system_prompt
        def add_project_details(ctx: RunContext[BlogPostGenerationContext]) -> str:
            project = ctx.deps.project_details
            return f"""
                Project Details:
                - Project Name: {project.name}
                - Project Type: {project.type}
                - Project Summary: {project.summary}
                - Blog Theme: {project.blog_theme}
                - Founders: {project.founders}
                - Key Features: {project.key_features}
                - Target Audience: {project.target_audience_summary}
                - Pain Points: {project.pain_points}
                - Product Usage: {project.product_usage}
            """

        @agent.system_prompt
        def add_project_pages(ctx: RunContext[BlogPostGenerationContext]) -> str:
            pages = ctx.deps.project_pages
            if pages:
                always_use_pages = [page for page in pages if page.always_use]
                optional_pages = [page for page in pages if not page.always_use]

                instruction = ""

                if always_use_pages:
                    instruction += """
                      REQUIRED PAGES TO LINK:
                      The following pages MUST be linked in the content you generate. These are essential pages that should be referenced in the blog post where contextually relevant:

                    """  # noqa: E501
                    for page in always_use_pages:
                        instruction += f"""
                          --------
                          - Title: {page.title}
                          - URL: {page.url}
                          - Description: {page.description}
                          - Summary: {page.summary}
                          --------
                        """

                if optional_pages:
                    instruction += """

                      OPTIONAL PAGES (Use Intelligently):
                      The following pages are available for linking if they are contextually relevant to the content. Use your judgment to determine which pages would provide value to readers and enhance the blog post. Only include links where they naturally fit and add value:

                    """  # noqa: E501
                    for page in optional_pages:
                        instruction += f"""
                          --------
                          - Title: {page.title}
                          - URL: {page.url}
                          - Description: {page.description}
                          - Summary: {page.summary}
                          --------
                        """

                return instruction
            else:
                return ""

        @agent.system_prompt
        def add_title_details(ctx: RunContext[BlogPostGenerationContext]) -> str:
            title = ctx.deps.title_suggestion
            return f"""
                This is the title suggestion gnerate by AI using project information:
                - Title: {title.title}
                - Description: {title.description}
                - Category: {title.category}
                - Target Keywords: {
                ", ".join(title.target_keywords) if title.target_keywords else "None specified"
            }
                - Suggested Meta Description: {
                title.suggested_meta_description
                if title.suggested_meta_description
                else "None specified"
            }
            """

        @agent.system_prompt
        def add_language_specification(ctx: RunContext[BlogPostGenerationContext]) -> str:
            return f"""
                IMPORTANT: Generate the content in {ctx.deps.project_details.language} language.
                Make sure the content is grammatically correct and culturally appropriate for
                {ctx.deps.project_details.language}-speaking audiences.
            """

        @agent.system_prompt
        def add_target_keywords(ctx: RunContext[BlogPostGenerationContext]) -> str:
            if ctx.deps.project_keywords:
                keywords_list = ", ".join(ctx.deps.project_keywords)
                return f"""
                    Focus Keywords for SEO
                    The user wants to focus on these specific keywords in the blog post:
                    {keywords_list}

                    Please incorporate these keywords naturally throughout the content where appropriate.
                    Don't force them in, but use them when they fit contextually and help improve the readability and SEO value of the post.
                    Don't make them bold, just a regular part of the text.
                """  # noqa: E501
            else:
                return ""

        @agent.system_prompt
        def valid_markdown_format() -> str:
            return """
                IMPORTANT: Generate the content in valid markdown format.
                Make sure the content is formatted correctly with:
                  - headings
                  - paragraphs
                  - lists
                  - links
            """

        @agent.system_prompt
        def post_structure() -> str:
            return """
                - Don't start with a title, header or a subheader (#, ##, ###). Instead start with a plain text as intro.
                - Use '##' (h2 headers) for sections of the post where necessary.
                - Don't use 3rd levle subheaders (###) or deeper. That should not be necessary for the post.
            """  # noqa: E501

        @agent.system_prompt
        def filler_content() -> str:
            return """
                - Do not add content that needs to be filled in later.
                - No placeholders either. This means no:
                  - Image Suggestion: [Image]
                  - Link Suggestion: [Link]
                  ...
             """

        # Get all analyzed project pages (from AI and sitemap sources)
        project_pages = [
            ProjectPageContext(
                url=page.url,
                title=page.title,
                description=page.description,
                summary=page.summary,
                always_use=page.always_use,
            )
            for page in self.project.project_pages.filter(date_analyzed__isnull=False)
        ]

        project_keywords = [
            pk.keyword.keyword_text
            for pk in self.project.project_keywords.filter(use=True).select_related("keyword")
        ]

        deps = BlogPostGenerationContext(
            project_details=self.project.project_details,
            title_suggestion=self.title_suggestion_schema,
            project_pages=project_pages,
            content_type=content_type,
            project_keywords=project_keywords,
        )

        result = run_agent_synchronously(
            agent,
            "Please generate an article based on the project details and title suggestions.",
            deps=deps,
            function_name="generate_content",
            model_name="BlogPostTitleSuggestion",
        )

        return GeneratedBlogPost.objects.create_and_validate(
            project=self.project,
            title=self,
            description=result.data.description,
            slug=result.data.slug,
            tags=result.data.tags,
            content=result.data.content,
        )


class AutoSubmissionSetting(BaseModel):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="auto_submission_settings"
    )
    endpoint_url = models.URLField(
        max_length=500, help_text="The endpoint to which posts will be automatically submitted."
    )
    body = models.JSONField(
        default=dict, blank=True, null=True, help_text="Key-value pairs for the request body."
    )
    header = models.JSONField(
        default=dict, blank=True, null=True, help_text="Key-value pairs for the request headers."
    )
    posts_per_month = models.PositiveIntegerField(
        default=1, help_text="How many posts to publish per month."
    )
    preferred_timezone = models.CharField(  # noqa: DJ001
        max_length=64,
        blank=True,
        null=True,
        help_text="Preferred timezone for publishing posts.",
    )
    preferred_time = models.TimeField(
        blank=True, null=True, help_text="Preferred time of day to publish posts."
    )

    def __str__(self):
        return f"{self.project.name}"


class GeneratedBlogPostManager(models.Manager):
    def create_and_validate(self, **kwargs):
        """Create a new blog post and validate it."""
        instance = self.create(**kwargs)
        instance.run_validation()
        return instance


class GeneratedBlogPost(BaseModel):
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="generated_blog_posts",
    )
    title = models.ForeignKey(
        BlogPostTitleSuggestion,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="generated_blog_posts",
    )
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=250)
    tags = models.TextField()
    content = models.TextField()
    icon = models.ImageField(upload_to="generated_blog_post_icons/", blank=True)
    image = models.ImageField(upload_to="generated_blog_post_images/", blank=True)

    posted = models.BooleanField(default=False)
    date_posted = models.DateTimeField(null=True, blank=True)

    # Validation Issues - Innocent until proven guilty
    content_too_short = models.BooleanField(default=False)
    has_valid_ending = models.BooleanField(default=True)
    placeholders = models.BooleanField(default=False)
    starts_with_header = models.BooleanField(default=False)

    objects = GeneratedBlogPostManager()

    def __str__(self):
        return f"{self.project.name}: {self.title.title}"

    @property
    def post_title(self):
        return self.title.title

    @property
    def blog_post_content_is_valid(self):
        return (
            self.content_too_short is False
            and self.has_valid_ending is True
            and self.placeholders is False
            and self.starts_with_header is False
        )

    @property
    def generated_blog_post_schema(self):
        return GeneratedBlogPostSchema(
            description=self.description,
            slug=self.slug,
            tags=self.tags,
            content=self.content,
        )

    def run_validation(self):
        """Run validation and update fields in a single query."""
        from core.utils import (
            blog_post_has_placeholders,
            blog_post_has_valid_ending,
            blog_post_starts_with_header,
        )

        base_logger_info = {
            "blog_post_id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name,
            "profile_id": self.project.profile.id,
            "profile_email": self.project.profile.user.email,
        }

        logger.info("[Validation] Running validation", **base_logger_info)

        if not self.content:
            self.content_too_short = True
            self.has_valid_ending = False
            self.placeholders = False
            self.starts_with_header = False

        else:
            content = self.content.strip()
            self.content_too_short = len(content) < 3000
            self.has_valid_ending = blog_post_has_valid_ending(self)
            self.placeholders = blog_post_has_placeholders(self)
            self.starts_with_header = blog_post_starts_with_header(self)

        self.save(
            update_fields=[
                "content_too_short",
                "has_valid_ending",
                "placeholders",
                "starts_with_header",
            ]
        )

        logger.info(
            "[Validation] Blog post validation complete",
            **base_logger_info,
            blog_post_title=self.title.title,
            content_too_short=self.content_too_short,
            has_valid_ending=self.has_valid_ending,
            placeholders=self.placeholders,
            starts_with_header=self.starts_with_header,
        )

    def fix_header_start(self):
        result = run_agent_synchronously(
            content_editor_agent,
            """
            This blog post starts with a header (like # or ##) instead of regular text.

            Please remove it such that the content starts with regular text, usually an introduction.
            """,  # noqa: E501
            deps=[
                self.generated_blog_post_schema,
                self.title.title_suggestion_schema,
            ],
            function_name="fix_header_start",
            model_name="GeneratedBlogPost",
        )

        self.content = result.data
        self.save(update_fields=["content"])
        self.run_validation()

        return True

    def submit_blog_post_to_endpoint(self):
        from core.utils import replace_placeholders

        project = self.project
        submission_settings = (
            AutoSubmissionSetting.objects.filter(project=project).order_by("-id").first()
        )

        if not submission_settings or not submission_settings.endpoint_url:
            logger.warning(
                "No AutoSubmissionSetting or endpoint_url found for project", project_id=project.id
            )
            return False

        url = submission_settings.endpoint_url
        headers = replace_placeholders(submission_settings.header, self)
        body = replace_placeholders(submission_settings.body, self)

        logger.info(
            "[Submit Blog Post] Submitting blog post to endpoint",
            project_id=project.id,
            profile_id=project.profile.id,
            endpoint_url=url,
            headers_configured=bool(headers),
            body_configured=bool(body),
        )

        try:
            session = requests.Session()
            session.cookies.clear()

            if headers is None:
                headers = {}

            if "content-type" not in headers and "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"

            response = session.post(url, json=body, headers=headers, timeout=15)
            response.raise_for_status()
            return True

        except requests.RequestException as e:
            logger.error(
                "[Submit Blog Post to Endpoint] Request error",
                error=str(e),
                url=url,
                headers=headers,
                exc_info=True,
            )
            return False

    def fix_content_length(self):
        result = run_agent_synchronously(
            content_editor_agent,
            """
            This blog post is too short.
            I think something went wrong during generation.
            Please regenerate.
          """,
            deps=[
                self.generated_blog_post_schema,
                self.title.title_suggestion_schema,
            ],
            function_name="fix_content_length",
            model_name="GeneratedBlogPost",
        )

        self.content = result.data
        self.save(update_fields=["content"])
        self.run_validation()

    def fix_valid_ending(self):
        result = run_agent_synchronously(
            content_editor_agent,
            """
            This blog post does not end on an ending that makes sense.
            Most likely generation failed at some point and returned half completed content.
            Please regenerate the blog post.
            """,
            deps=[
                self.generated_blog_post_schema,
                self.title.title_suggestion_schema,
            ],
            function_name="fix_valid_ending",
            model_name="GeneratedBlogPost",
        )

        self.content = result.data
        self.save(update_fields=["content"])
        self.run_validation()

    def fix_placeholders(self):
        result = run_agent_synchronously(
            content_editor_agent,
            """
            The content contains placeholders.
            Please regenerate the blog post without placeholders.
            """,
            deps=[
                self.generated_blog_post_schema,
                self.title.title_suggestion_schema,
            ],
            function_name="fix_placeholders",
            model_name="GeneratedBlogPost",
        )

        self.content = result.data
        self.save(update_fields=["content"])
        self.run_validation()

    def fix_generated_blog_post(self):
        if self.content_too_short is True:
            self.fix_content_length()

        if self.has_valid_ending is False:
            self.fix_valid_ending()

        if self.placeholders is True:
            self.fix_placeholders()

        if self.starts_with_header is True:
            self.fix_header_start()


class ProjectPage(BaseModel):
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.CASCADE, related_name="project_pages"
    )

    url = models.URLField(max_length=200)
    source = models.CharField(
        max_length=20,
        choices=ProjectPageSource.choices,
        default=ProjectPageSource.AI,
        help_text="Source of the page: AI-discovered or from Sitemap",
    )

    # Content from Jina Reader
    date_scraped = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=500, blank=True, default="")
    description = models.TextField(blank=True, default="")
    markdown_content = models.TextField(blank=True, default="")

    # AI Content
    date_analyzed = models.DateTimeField(null=True, blank=True)
    type = models.CharField(max_length=255, choices=ProjectPageType.choices, blank=True, default="")
    type_ai_guess = models.CharField(max_length=255)
    summary = models.TextField(blank=True)

    # Link usage in blog posts
    always_use = models.BooleanField(
        default=False,
        help_text="When enabled, this page link will always be included in generated blog posts",
    )

    def __str__(self):
        return f"{self.project.name}: {self.title}"

    class Meta:
        unique_together = ("project", "url")

    def clean(self):
        """Validate that the URL is valid before saving."""
        from django.core.exceptions import ValidationError

        if not self.url:
            raise ValidationError("URL cannot be empty")

        if not isinstance(self.url, str):
            raise ValidationError("URL must be a string")

        if not self.url.startswith(("http://", "https://")):
            raise ValidationError(
                f"Invalid URL: {self.url}. URL must start with http:// or https://"
            )

        # Check if URL looks like an error message or invalid content
        if any(
            phrase in self.url.lower()
            for phrase in ["i need", "please provide", "error", "invalid", "missing"]
        ):
            raise ValidationError(f"Invalid URL content detected: {self.url}")

    def save(self, *args, **kwargs):
        """Override save to validate URL before saving."""
        self.clean()
        super().save(*args, **kwargs)

    @property
    def web_page_content(self):
        return WebPageContent(
            title=self.title,
            description=self.description,
            markdown_content=self.markdown_content,
        )

    def get_page_content(self):
        """
        Fetch page content using Jina Reader API and update the project.
        Returns the content if successful, raises ValueError otherwise.
        """
        title, description, markdown_content = get_markdown_content(self.url)

        if not title or not description or not markdown_content:
            return False

        self.date_scraped = timezone.now()
        self.title = title
        self.description = description
        self.markdown_content = markdown_content

        self.save(
            update_fields=[
                "date_scraped",
                "title",
                "description",
                "markdown_content",
            ]
        )

        return True

    def analyze_content(self):
        """
        Analyze the page content using Claude via PydanticAI and update project details.
        Should be called after get_page_content().
        """
        from core.agents import summarize_page_agent

        webpage_content = WebPageContent(
            title=self.title,
            description=self.description,
            markdown_content=self.markdown_content,
        )

        analysis_result = run_agent_synchronously(
            summarize_page_agent,
            "Please analyze this web page.",
            deps=webpage_content,
            function_name="analyze_content",
            model_name="ProjectPage",
        )

        self.date_analyzed = timezone.now()

        if self.type == "":
            self.type = analysis_result.data.type

        self.type_ai_guess = analysis_result.data.type_ai_guess
        self.summary = analysis_result.data.summary
        self.save(
            update_fields=[
                "date_analyzed",
                "type",
                "type_ai_guess",
                "summary",
            ]
        )

        return True


class Competitor(BaseModel):
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.CASCADE, related_name="competitors"
    )
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=200)
    description = models.TextField()

    date_scraped = models.DateTimeField(null=True, blank=True)
    homepage_title = models.CharField(max_length=500, blank=True, default="")
    homepage_description = models.TextField(blank=True, default="")
    markdown_content = models.TextField(blank=True)
    summary = models.TextField(blank=True)

    date_analyzed = models.DateTimeField(null=True, blank=True)
    # how does this competitor compare to the project?
    competitor_analysis = models.TextField(blank=True)
    key_differences = models.TextField(blank=True)
    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)
    opportunities = models.TextField(blank=True)
    threats = models.TextField(blank=True)
    key_features = models.TextField(blank=True)
    key_benefits = models.TextField(blank=True)
    key_drawbacks = models.TextField(blank=True)
    links = models.JSONField(default=list, blank=True, null=True)

    def __str__(self):
        return f"{self.name}"

    @property
    def competitor_details(self):
        return CompetitorDetails(
            name=self.name,
            url=self.url,
            description=self.description,
        )

    def get_page_content(self):
        """
        Fetch page content using Jina Reader API and update the project.
        Returns the content if successful, raises ValueError otherwise.
        """
        homepage_title, homepage_description, markdown_content = get_markdown_content(self.url)

        if not homepage_title or not homepage_description or not markdown_content:
            return False

        self.date_scraped = timezone.now()
        self.homepage_title = homepage_title
        self.homepage_description = homepage_description
        self.markdown_content = markdown_content

        self.save(
            update_fields=[
                "date_scraped",
                "homepage_title",
                "homepage_description",
                "markdown_content",
            ]
        )

        return True

    def populate_name_description(self):
        agent = Agent(
            "google-gla:gemini-2.5-flash",
            output_type=CompetitorDetails,
            deps_type=WebPageContent,
            system_prompt=(
                """
                You are an expert marketer.
                Based on the competitor details and homepage content provided,
                extract and infer the requested information. Make reasonable inferences based
                on available content, context, and industry knowledge.
                """
            ),
            retries=2,
        )

        @agent.system_prompt
        def add_webpage_content(ctx: RunContext[WebPageContent]) -> str:
            return f"Web page content:Content: {ctx.deps.markdown_content}"

        deps = WebPageContent(
            title=self.homepage_title,
            description=self.homepage_description,
            markdown_content=self.markdown_content,
        )
        result = run_agent_synchronously(
            agent,
            "Please analyze this competitor and extract the key information.",
            deps=deps,
            function_name="populate_name_description",
            model_name="Competitor",
        )

        self.name = result.data.name
        self.description = result.data.description
        self.save(update_fields=["name", "description"])

        return True

    def analyze_competitor(self):
        agent = Agent(
            "google-gla:gemini-2.5-flash",
            output_type=CompetitorAnalysis,
            deps_type=CompetitorAnalysisContext,
            system_prompt=(
                """
                You are an expert marketer.
                Based on the competitor details and homepage content provided,
                extract and infer the requested information. Make reasonable inferences based
                on available content, context, and industry knowledge.
                """
            ),
            retries=2,
            model_settings={"temperature": 0.8},
        )

        @agent.system_prompt
        def add_todays_date() -> str:
            return f"Today's Date: {timezone.now().strftime('%Y-%m-%d')}"

        @agent.system_prompt
        def my_project_details(ctx: RunContext[CompetitorAnalysisContext]) -> str:
            project = ctx.deps.project_details
            return f"""
                Project Details:
                - Project Name: {project.name}
                - Project Type: {project.type}
                - Project Summary: {project.summary}
                - Blog Theme: {project.blog_theme}
                - Founders: {project.founders}
                - Key Features: {project.key_features}
                - Target Audience: {project.target_audience_summary}
                - Pain Points: {project.pain_points}
                - Product Usage: {project.product_usage}
            """

        @agent.system_prompt
        def competitor_details(ctx: RunContext[CompetitorAnalysisContext]) -> str:
            competitor = ctx.deps.competitor_details
            return f"""
                Competitor Details:
                - Competitor Name: {competitor.name}
                - Competitor URL: {competitor.url}
                - Competitor Description: {competitor.description}
                - Competitor Homepage Content: {ctx.deps.competitor_homepage_content}
            """

        deps = CompetitorAnalysisContext(
            project_details=self.project.project_details,
            competitor_details=self.competitor_details,
            competitor_homepage_content=self.markdown_content,
        )
        result = run_agent_synchronously(
            agent,
            "Please analyze this competitor and extract the key information.",
            deps=deps,
            function_name="analyze_competitor",
            model_name="Competitor",
        )

        self.competitor_analysis = result.data.competitor_analysis
        self.key_differences = result.data.key_differences
        self.strengths = result.data.strengths
        self.summary = result.data.summary
        self.weaknesses = result.data.weaknesses
        self.opportunities = result.data.opportunities
        self.threats = result.data.threats
        self.key_features = result.data.key_features
        self.key_benefits = result.data.key_benefits
        self.key_drawbacks = result.data.key_drawbacks
        self.links = result.data.links
        self.date_analyzed = timezone.now()
        self.save()

        return True


class Keyword(BaseModel):
    keyword_text = models.CharField(max_length=255, help_text="The keyword string")
    volume = models.IntegerField(
        null=True, blank=True, help_text="The search volume of the keyword"
    )
    cpc_currency = models.CharField(
        max_length=10, blank=True, help_text="The currency of the CPC value"
    )
    cpc_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, help_text="The cost per click value"
    )
    competition = models.FloatField(
        null=True, blank=True, help_text="The competition metric of the keyword (0 to 1)"
    )
    country = models.CharField(
        max_length=10,
        blank=True,
        default="us",
        help_text="The country for which metrics were fetched",
    )
    data_source = models.CharField(
        max_length=3,
        choices=KeywordDataSource.choices,
        default=KeywordDataSource.GOOGLE_KEYWORD_PLANNER,
        blank=True,
        help_text="The data source for the keyword metrics",
    )
    last_fetched_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp of when the data was last fetched"
    )
    got_related_keywords = models.BooleanField(default=False)
    got_people_also_search_for_keywords = models.BooleanField(default=False)

    class Meta:
        unique_together = ("keyword_text", "country", "data_source")
        verbose_name = "Keyword"
        verbose_name_plural = "Keywords"

    def __str__(self):
        return f"{self.keyword_text} ({self.country or 'global'} - {self.data_source or 'N/A'})"

    def fetch_and_update_metrics(self, currency="usd"):  # noqa: C901
        if not hasattr(settings, "KEYWORDS_EVERYWHERE_API_KEY"):
            logger.error("[KeywordFetch] KEYWORDS_EVERYWHERE_API_KEY not found in settings.")
            return False

        api_key = settings.KEYWORDS_EVERYWHERE_API_KEY
        api_url = "https://api.keywordseverywhere.com/v1/get_keyword_data"

        payload = {
            "kw[]": [self.keyword_text],
            "country": self.country,
            "currency": currency,
            "dataSource": self.data_source,
        }
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}

        try:
            response = requests.post(api_url, data=payload, headers=headers, timeout=30)
            response.raise_for_status()

            response_data = response.json()

            if (
                not response_data.get("data")
                or not isinstance(response_data["data"], list)
                or not response_data["data"][0]
            ):
                logger.warning(
                    "[KeywordFetch] No data found in API response for keyword.",
                    keyword_id=self.id,
                    keyword_text=self.keyword_text,
                    response_status=response.status_code,
                    response_content=response.text[:500],
                )
                return False

            keyword_api_data = response_data["data"][0]

            self.volume = keyword_api_data.get("vol")

            cpc_data = keyword_api_data.get("cpc", {})
            self.cpc_currency = cpc_data.get("currency", "")
            try:
                self.cpc_value = Decimal(str(cpc_data.get("value", "0.00")))
            except InvalidOperation:
                logger.warning(
                    "[KeywordFetch] Invalid CPC value for keyword.",
                    keyword_text=self.keyword_text,
                    keyword_id=self.id,
                    cpc_value_raw=cpc_data.get("value"),
                )
                self.cpc_value = Decimal("0.00")

            self.competition = keyword_api_data.get("competition")
            self.last_fetched_at = timezone.now()

            # Save keyword instance before handling trends to ensure FK exists
            self.save(
                update_fields=[
                    "volume",
                    "cpc_currency",
                    "cpc_value",
                    "competition",
                    "last_fetched_at",
                ]
            )

            trend_data = keyword_api_data.get("trend", [])
            if isinstance(trend_data, list):
                with transaction.atomic():
                    # Get a set of existing (month, year) tuples for efficient lookup
                    existing_trends_tuples = set(self.trends.values_list("month", "year"))

                    trends_to_create = []
                    for trend_item in trend_data:
                        if (
                            isinstance(trend_item, dict)
                            and "month" in trend_item
                            and "year" in trend_item
                            and "value" in trend_item
                        ):
                            month_str = str(trend_item["month"])
                            year_int = int(trend_item["year"])

                            # Check if this month/year combo already exists
                            if (month_str, year_int) not in existing_trends_tuples:
                                trends_to_create.append(
                                    KeywordTrend(
                                        keyword=self,
                                        month=month_str,
                                        year=year_int,
                                        value=int(trend_item["value"]),
                                    )
                                )
                    if trends_to_create:
                        KeywordTrend.objects.bulk_create(trends_to_create)

            return True

        except requests.exceptions.HTTPError as e:
            logger.error(
                "[KeywordFetch] HTTP error occurred.",
                keyword_id=self.id,
                keyword_text=self.keyword_text,
                error=str(e),
                exc_info=True,
                status_code=e.response.status_code if e.response else None,
                response_content=e.response.text[:500] if e.response else None,
            )
            # Specific handling for API error codes
            if e.response is not None:
                if e.response.status_code == 401:
                    logger.error("[KeywordFetch] API Key is missing or invalid.")
                elif e.response.status_code == 402:
                    logger.error("[KeywordFetch] Insufficient credits or invalid subscription.")
                elif e.response.status_code == 400:
                    logger.error("[KeywordFetch] Submitted request data is invalid.")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(
                "[KeywordFetch] Request exception occurred.",
                keyword_id=self.id,
                keyword_text=self.keyword_text,
                error=str(e),
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                "[KeywordFetch] An unexpected error occurred.",
                keyword_id=self.id,
                keyword_text=self.keyword_text,
                error=str(e),
                exc_info=True,
            )
            return False


class ProjectKeyword(BaseModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_keywords")
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE, related_name="keyword_projects")
    use = models.BooleanField(default=False)
    date_associated = models.DateTimeField(
        auto_now_add=True, help_text="When the keyword was associated with the project"
    )

    class Meta:
        unique_together = ("project", "keyword")
        verbose_name = "Project Keyword"
        verbose_name_plural = "Project Keywords"

    def __str__(self):
        return f"{self.project.name} - {self.keyword.keyword_text}"


class KeywordTrend(BaseModel):
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE, related_name="trends")
    month = models.CharField(max_length=10, help_text="The month of this volume (e.g., May)")
    year = models.IntegerField(help_text="The year of this volume (e.g., 2019)")
    value = models.IntegerField(help_text="The search volume of the keyword for the given month")

    class Meta:
        unique_together = ("keyword", "month", "year")
        verbose_name = "Keyword Trend"
        verbose_name_plural = "Keyword Trends"
        ordering = ["keyword", "year", "month"]

    def __str__(self):
        return f"{self.keyword.keyword_text} - {self.month} {self.year}: {self.value}"


class Feedback(BaseModel):
    profile = models.ForeignKey(
        Profile, null=True, blank=True, on_delete=models.CASCADE, related_name="feedback"
    )
    feedback = models.TextField()
    page = models.CharField(max_length=255)
    date_submitted = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.profile.user.email}: {self.feedback}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new:
            from django.conf import settings
            from django.core.mail import send_mail

            subject = "New Feedback Submitted"
            message = f"""
                New feedback was submitted:
                User: {self.profile.user.email if self.profile else "Anonymous"}
                Feedback: {self.feedback}
                Page: {self.page}
            """
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = ["kireevr1996@gmail.com"]

            send_mail(subject, message, from_email, recipient_list, fail_silently=True)
