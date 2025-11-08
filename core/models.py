import json
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django_q.tasks import async_task
from pgvector.django import HnswIndex, VectorField
from pydantic_ai import Agent, RunContext

from core.base_models import BaseModel
from core.choices import (
    BlogPostStatus,
    Category,
    ContentType,
    EmailType,
    KeywordDataSource,
    Language,
    OGImageStyle,
    ProfileStates,
    ProjectPageSource,
    ProjectPageType,
    ProjectStyle,
    ProjectType,
    get_default_ai_model,
)
from core.model_utils import (
    generate_random_key,
    get_markdown_content,
    run_agent_synchronously,
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
        return self.product_name == "Free" and not self.user.is_superuser

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

    @property
    def competitor_limit(self):
        """Maximum number of competitors a user can have across all projects."""
        if self.is_on_free_plan:
            return 5
        return None

    @property
    def competitor_posts_limit(self):
        """Maximum number of competitor VS blog posts a user can generate."""
        if self.is_on_free_plan:
            return 3
        return None

    @property
    def number_of_competitors(self):
        """Total number of competitors across all projects."""
        projects = self.projects.all()
        return sum(project.competitors.count() for project in projects)

    @property
    def number_of_competitor_posts_generated(self):
        """Total number of competitor VS blog posts that have been generated."""
        projects = self.projects.all()
        competitor_posts_count = 0
        for project in projects:
            competitor_posts_count += (
                project.competitors.filter(blog_post__isnull=False).exclude(blog_post="").count()
            )
        return competitor_posts_count

    @property
    def reached_competitor_limit(self):
        limit = self.competitor_limit
        if limit is None:
            return False
        return self.number_of_competitors >= limit

    @property
    def reached_competitor_posts_limit(self):
        limit = self.competitor_posts_limit
        if limit is None:
            return False
        return self.number_of_competitor_posts_generated >= limit

    @property
    def can_add_competitors(self):
        return not self.reached_competitor_limit

    @property
    def can_generate_competitor_posts(self):
        return not self.reached_competitor_posts_limit


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
    enable_automatic_og_image_generation = models.BooleanField(default=True)
    og_image_style = models.CharField(
        max_length=50,
        choices=OGImageStyle.choices,
        default=OGImageStyle.MODERN_GRADIENT,
        blank=True,
    )

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
            is_on_free_plan=self.profile.is_on_free_plan,
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
        from core.agents.analyze_project_agent import agent

        result = run_agent_synchronously(
            agent,
            "Analyze this web page content and extract the key information.",
            deps=WebPageContent(
                title=self.title,
                description=self.description,
                markdown_content=self.markdown_content,
            ),
            function_name="analyze_content",
            model_name="Project",
        )

        self.name = result.output.name
        self.type = result.output.type
        self.summary = result.output.summary
        self.blog_theme = result.output.blog_theme
        self.founders = result.output.founders
        self.key_features = result.output.key_features
        self.target_audience_summary = result.output.target_audience_summary
        self.pain_points = result.output.pain_points
        self.product_usage = result.output.product_usage
        self.links = result.output.links
        self.language = result.output.language
        self.proposed_keywords = result.output.proposed_keywords
        self.location = result.output.location
        self.date_analyzed = timezone.now()
        self.save()

        async_task("core.tasks.generate_blog_post_suggestions", self.id)
        async_task("core.tasks.process_project_keywords", self.id)
        async_task("core.tasks.schedule_project_page_analysis", self.id)
        async_task("core.tasks.schedule_project_competitor_analysis", self.id, timeout=180)

        return True

    def generate_title_suggestions(self, num_titles=3, user_prompt="", model=None):
        from core.agents.title_suggestions_agent import agent as title_suggestions_agent

        if model:
            title_suggestions_agent.model = model

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
            title_suggestions_agent,
            "Please generate blog post title suggestions based on the project details.",
            deps=deps,
            function_name="generate_title_suggestions",
            model_name="Project",
        )

        with transaction.atomic():
            suggestions = []
            for title in result.output.titles:
                suggestion = BlogPostTitleSuggestion(
                    project=self,
                    title=title.title,
                    description=title.description,
                    category=title.category,
                    content_type=ContentType.SEO,
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

    def get_a_list_of_links(self, model=None):
        agent = Agent(
            model or get_default_ai_model(),
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

        return result.output

    def find_competitors(self):
        from core.agents.competitor_finder_agent import agent

        result = run_agent_synchronously(
            agent,
            "Give me a list of sites that might be considered my competition.",
            deps=self.project_details,
            function_name="find_competitors",
            model_name="Project",
        )

        self.competitors_list = result.output
        self.save(update_fields=["competitors_list"])

        return result.output

    def get_and_save_list_of_competitors(self, model=None):
        agent = Agent(
            model or get_default_ai_model(),
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
        for competitor in result.output:
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
        max_length=20, choices=ContentType.choices, default=ContentType.SEO
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

    def start_generation_pipeline(self):
        """
        Initialize a new blog post generation pipeline.

        Creates a GeneratedBlogPost with initialized pipeline state.
        Returns the blog post object ready for pipeline execution.
        """
        blog_post = GeneratedBlogPost.objects.create(
            project=self.project,
            title=self,
            description="",
            slug="",
            tags="",
            content="",
        )

        blog_post.initialize_pipeline()

        logger.info(
            "[Pipeline] Started generation pipeline",
            blog_post_id=blog_post.id,
            project_id=self.project_id,
            title_suggestion_id=self.id,
            title=self.title,
        )

        return blog_post

    def generate_structure(self, blog_post):
        """
        Step 1: Generate the blog post structure/outline.

        Args:
            blog_post: The GeneratedBlogPost object to update

        Returns:
            The structure as a JSON-serializable dict
        """
        from core.agents.blog_structure_agent import agent

        blog_post.update_pipeline_step("generate_structure", "in_progress")

        try:
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
                content_type=self.content_type,
                project_keywords=project_keywords,
            )

            result = run_agent_synchronously(
                agent,
                "Please create a comprehensive structure outline for this blog post.",
                deps=deps,
                function_name="generate_structure",
                model_name="BlogPostTitleSuggestion",
            )

            # Convert structure to dict for JSON storage
            structure_dict = result.output.model_dump()

            # Save structure to blog post
            blog_post.generation_structure = json.dumps(structure_dict, indent=2)
            blog_post.save(update_fields=["generation_structure"])

            blog_post.update_pipeline_step("generate_structure", "completed")

            logger.info(
                "[Pipeline] Structure generation completed",
                blog_post_id=blog_post.id,
                sections_count=len(structure_dict.get("sections", [])),
            )

            return structure_dict

        except Exception as error:
            blog_post.update_pipeline_step(
                "generate_structure",
                "failed",
                error=str(error),
            )
            logger.error(
                "[Pipeline] Structure generation failed",
                blog_post_id=blog_post.id,
                error=str(error),
                exc_info=True,
            )
            raise

    def generate_content_from_structure(self, blog_post):
        """
        Step 2: Generate the full blog post content based on the structure.

        Args:
            blog_post: The GeneratedBlogPost object with structure already generated

        Returns:
            The generated content as a string
        """
        from core.agents.seo_content_generator_agent import (
            agent,
            create_structure_guidance_prompt,
        )

        blog_post.update_pipeline_step("generate_content", "in_progress")

        try:
            # Load the structure
            structure_dict = json.loads(blog_post.generation_structure)

            # Add structure-specific system prompt to agent
            structure_prompt = create_structure_guidance_prompt(structure_dict)
            agent.system_prompt(structure_prompt)

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
                content_type=self.content_type,
                project_keywords=project_keywords,
            )

            result = run_agent_synchronously(
                agent,
                "Please generate the full blog post content following the provided structure outline.",  # noqa: E501
                deps=deps,
                function_name="generate_content_from_structure",
                model_name="BlogPostTitleSuggestion",
            )

            # Update blog post with generated content
            blog_post.description = result.output.description
            blog_post.slug = result.output.slug
            blog_post.tags = result.output.tags
            blog_post.raw_content = result.output.content
            blog_post.content = result.output.content
            blog_post.save(update_fields=["description", "slug", "tags", "raw_content", "content"])

            blog_post.update_pipeline_step("generate_content", "completed")

            logger.info(
                "[Pipeline] Content generation completed",
                blog_post_id=blog_post.id,
                content_length=len(result.output.content),
            )

            return result.output.content

        except Exception as error:
            blog_post.update_pipeline_step(
                "generate_content",
                "failed",
                error=str(error),
            )
            logger.error(
                "[Pipeline] Content generation failed",
                blog_post_id=blog_post.id,
                error=str(error),
                exc_info=True,
            )
            raise

    def run_preliminary_validation(self, blog_post):
        """
        Step 3: Run preliminary validation on the generated content using AI.

        Args:
            blog_post: The GeneratedBlogPost object with content

        Returns:
            bool: True if validation passed, False otherwise
        """
        from core.agents.content_validation_agent import agent
        from core.model_utils import run_agent_synchronously

        blog_post.update_pipeline_step("preliminary_validation", "in_progress")

        try:
            result = run_agent_synchronously(
                agent,
                blog_post.content,
                function_name="run_preliminary_validation",
            )

            validation_result = result.output
            is_valid = validation_result.is_valid

            if is_valid:
                blog_post.update_pipeline_step("preliminary_validation", "completed")
                logger.info(
                    "[Pipeline] Preliminary validation passed",
                    blog_post_id=blog_post.id,
                )
            else:
                issues_text = "; ".join(validation_result.validation_issues)
                blog_post.update_pipeline_step(
                    "preliminary_validation",
                    "failed",
                    error=f"Content validation failed - {issues_text}",
                )
                logger.warning(
                    "[Pipeline] Preliminary validation failed",
                    blog_post_id=blog_post.id,
                    validation_issues=validation_result.validation_issues,
                )

            return {
                "is_valid": is_valid,
                "validation_issues": validation_result.validation_issues if not is_valid else [],
            }

        except Exception as error:
            blog_post.update_pipeline_step(
                "preliminary_validation",
                "failed",
                error=str(error),
            )
            logger.error(
                "[Pipeline] Preliminary validation error",
                blog_post_id=blog_post.id,
                error=str(error),
                exc_info=True,
            )
            raise

    def fix_preliminary_validation(self, blog_post, validation_issues):
        """
        Fix content issues identified during preliminary validation.

        Args:
            blog_post: The GeneratedBlogPost object with content
            validation_issues: List of validation issues to fix

        Returns:
            Fixed content
        """
        from core.agents.fix_validation_issue_agent import agent
        from core.model_utils import run_agent_synchronously
        from core.schemas import ContentFixContext

        blog_post.update_pipeline_step("fix_preliminary_validation", "in_progress")

        try:
            context = ContentFixContext(
                content=blog_post.content,
                validation_issues=validation_issues,
            )

            result = run_agent_synchronously(
                agent,
                context,
            )

            fixed_content = result.output

            blog_post.content = fixed_content
            blog_post.save(update_fields=["content"])

            blog_post.update_pipeline_step("fix_preliminary_validation", "completed")
            logger.info(
                "[Pipeline] Fixed preliminary validation issues",
                blog_post_id=blog_post.id,
            )

            return fixed_content

        except Exception as error:
            blog_post.update_pipeline_step(
                "fix_preliminary_validation",
                "failed",
                error=str(error),
            )
            logger.error(
                "[Pipeline] Error fixing preliminary validation issues",
                blog_post_id=blog_post.id,
                error=str(error),
                exc_info=True,
            )
            raise

    def insert_internal_links(self, blog_post):
        """
        Step 4: Insert internal links into the content.

        Args:
            blog_post: The GeneratedBlogPost object with validated content

        Returns:
            Content with internal links inserted
        """
        from core.agents.internal_links_agent import agent
        from core.schemas import InternalLinkContext

        blog_post.update_pipeline_step("insert_internal_links", "in_progress")

        try:
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

            if not project_pages:
                logger.info(
                    "[Pipeline] No project pages available for internal links, skipping",
                    blog_post_id=blog_post.id,
                )
                blog_post.update_pipeline_step("insert_internal_links", "completed")
                return blog_post.content

            deps = InternalLinkContext(
                content=blog_post.content,
                available_pages=project_pages,
            )

            result = run_agent_synchronously(
                agent,
                "Please insert relevant internal links into this content.",
                deps=deps,
                function_name="insert_internal_links",
                model_name="BlogPostTitleSuggestion",
            )

            # Update blog post with content that has internal links
            blog_post.content = result.output
            blog_post.save(update_fields=["content"])

            blog_post.update_pipeline_step("insert_internal_links", "completed")

            logger.info(
                "[Pipeline] Internal links insertion completed",
                blog_post_id=blog_post.id,
            )

            return result.output

        except Exception as error:
            blog_post.update_pipeline_step(
                "insert_internal_links",
                "failed",
                error=str(error),
            )
            logger.error(
                "[Pipeline] Internal links insertion failed",
                blog_post_id=blog_post.id,
                error=str(error),
                exc_info=True,
            )
            raise

    def run_final_validation(self, blog_post):
        """
        Step 5: Run final validation on the complete content with internal links using AI.

        Args:
            blog_post: The GeneratedBlogPost object with final content

        Returns:
            bool: True if validation passed, False otherwise
        """
        from core.agents.content_validation_agent import agent
        from core.model_utils import run_agent_synchronously

        blog_post.update_pipeline_step("final_validation", "in_progress")

        try:
            result = run_agent_synchronously(
                agent,
                blog_post.content,
                function_name="run_final_validation",
            )

            validation_result = result.output
            is_valid = validation_result.is_valid

            if is_valid:
                blog_post.update_pipeline_step("final_validation", "completed")
                logger.info(
                    "[Pipeline] Final validation passed - blog post ready",
                    blog_post_id=blog_post.id,
                )
            else:
                issues_text = "; ".join(validation_result.validation_issues)
                blog_post.update_pipeline_step(
                    "final_validation",
                    "failed",
                    error=f"Content validation failed - {issues_text}",
                )
                logger.warning(
                    "[Pipeline] Final validation failed",
                    blog_post_id=blog_post.id,
                    validation_issues=validation_result.validation_issues,
                )

            return {
                "is_valid": is_valid,
                "validation_issues": validation_result.validation_issues if not is_valid else [],
            }

        except Exception as error:
            blog_post.update_pipeline_step(
                "final_validation",
                "failed",
                error=str(error),
            )
            logger.error(
                "[Pipeline] Final validation error",
                blog_post_id=blog_post.id,
                error=str(error),
                exc_info=True,
            )
            raise

    def fix_final_validation(self, blog_post, validation_issues):
        """
        Fix content issues identified during final validation.

        Args:
            blog_post: The GeneratedBlogPost object with content
            validation_issues: List of validation issues to fix

        Returns:
            Fixed content
        """
        from core.agents.fix_validation_issue_agent import agent
        from core.model_utils import run_agent_synchronously
        from core.schemas import ContentFixContext

        blog_post.update_pipeline_step("fix_final_validation", "in_progress")

        try:
            context = ContentFixContext(
                content=blog_post.content,
                validation_issues=validation_issues,
            )

            result = run_agent_synchronously(
                agent,
                context,
            )

            fixed_content = result.output

            blog_post.content = fixed_content
            blog_post.save(update_fields=["content"])

            blog_post.update_pipeline_step("fix_final_validation", "completed")
            logger.info(
                "[Pipeline] Fixed final validation issues",
                blog_post_id=blog_post.id,
            )

            return fixed_content

        except Exception as error:
            blog_post.update_pipeline_step(
                "fix_final_validation",
                "failed",
                error=str(error),
            )
            logger.error(
                "[Pipeline] Error fixing final validation issues",
                blog_post_id=blog_post.id,
                error=str(error),
                exc_info=True,
            )
            raise

    def execute_complete_pipeline(self):
        """
        Execute the complete blog post generation pipeline sequentially.

        This method runs all steps without UI updates, suitable for scheduled tasks.
        Returns the final GeneratedBlogPost or raises an exception on failure.
        """
        logger.info(
            "[Pipeline] Starting complete pipeline execution",
            title_suggestion_id=self.id,
            project_id=self.project_id,
            title=self.title,
        )

        blog_post = self.start_generation_pipeline()

        try:
            # Step 1: Generate structure
            self.generate_structure(blog_post)

            # Step 2: Generate content
            self.generate_content_from_structure(blog_post)

            # Step 3: Preliminary validation
            validation_result = self.run_preliminary_validation(blog_post)
            if not validation_result["is_valid"]:
                logger.warning(
                    "[Pipeline] Preliminary validation failed, attempting to fix",
                    blog_post_id=blog_post.id,
                )
                self.fix_preliminary_validation(blog_post, validation_result["validation_issues"])

            # Step 4: Insert internal links
            self.insert_internal_links(blog_post)

            # Step 5: Final validation
            validation_result = self.run_final_validation(blog_post)
            if not validation_result["is_valid"]:
                logger.warning(
                    "[Pipeline] Final validation failed, attempting to fix",
                    blog_post_id=blog_post.id,
                )
                self.fix_final_validation(blog_post, validation_result["validation_issues"])
                # Re-run final validation after fixing
                validation_result = self.run_final_validation(blog_post)
                if not validation_result["is_valid"]:
                    logger.error(
                        "[Pipeline] Final validation still failed after fix",
                        blog_post_id=blog_post.id,
                    )

            # Generate OG image if enabled
            if self.project.enable_automatic_og_image_generation:
                async_task(
                    "core.tasks.generate_og_image_for_blog_post",
                    blog_post.id,
                    group="Generate OG Image",
                )

            logger.info(
                "[Pipeline] Complete pipeline execution successful",
                blog_post_id=blog_post.id,
                title_suggestion_id=self.id,
            )

            return blog_post

        except Exception as error:
            logger.error(
                "[Pipeline] Complete pipeline execution failed",
                blog_post_id=blog_post.id,
                title_suggestion_id=self.id,
                error=str(error),
                exc_info=True,
            )
            raise


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

    # Pipeline fields
    pipeline_state = models.JSONField(
        null=True,
        blank=True,
        default=None,
        help_text="Tracks the current step and status of the generation pipeline",
    )
    generation_structure = models.TextField(
        blank=True,
        default="",
        help_text="Stores the outline/structure from the first pipeline step",
    )
    raw_content = models.TextField(
        blank=True,
        default="",
        help_text="Stores content before internal links are added",
    )
    pipeline_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Stores timestamps, AI model info, and token usage per step",
    )

    objects = GeneratedBlogPostManager()

    def __str__(self):
        return f"{self.project.name}: {self.title.title}"

    @property
    def post_title(self):
        return self.title.title

    @property
    def generated_blog_post_schema(self):
        return GeneratedBlogPostSchema(
            description=self.description,
            slug=self.slug,
            tags=self.tags,
            content=self.content,
        )

    @property
    def is_ready_to_view(self):
        """Check if the blog post has passed final validation and is ready to view."""
        if not self.content:
            return False
        if not self.pipeline_state:
            return True
        final_validation_status = (
            self.pipeline_state.get("steps", {}).get("final_validation", {}).get("status")
        )
        return final_validation_status == "completed"

    def _build_fix_context(self):
        """Build full context for content editor agent to ensure accurate regeneration."""

        project_pages = [
            ProjectPageContext(
                url=page.url,
                title=page.title,
                description=page.description,
                summary=page.summary,
            )
            for page in self.project.project_pages.all()
        ]

        project_keywords = [
            pk.keyword.keyword_text
            for pk in self.project.project_keywords.filter(use=True).select_related("keyword")
        ]

        return BlogPostGenerationContext(
            project_details=self.project.project_details,
            title_suggestion=self.title.title_suggestion_schema,
            project_pages=project_pages,
            content_type=self.title.content_type,
            project_keywords=project_keywords,
        )

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

    def initialize_pipeline(self):
        """Initialize the pipeline state for a new blog post generation."""
        initial_pipeline_state = {
            "current_step": "generate_structure",
            "steps": {
                "generate_structure": {"status": "pending", "retry_count": 0, "error": None},
                "generate_content": {"status": "pending", "retry_count": 0, "error": None},
                "preliminary_validation": {"status": "pending", "retry_count": 0, "error": None},
                "fix_preliminary_validation": {
                    "status": "pending",
                    "retry_count": 0,
                    "error": None,
                },
                "insert_internal_links": {"status": "pending", "retry_count": 0, "error": None},
                "final_validation": {"status": "pending", "retry_count": 0, "error": None},
                "fix_final_validation": {"status": "pending", "retry_count": 0, "error": None},
            },
        }
        self.pipeline_state = initial_pipeline_state
        self.pipeline_metadata = {
            "started_at": timezone.now().isoformat(),
            "steps_completed": 0,
            "total_steps": 5,
        }
        self.save(update_fields=["pipeline_state", "pipeline_metadata"])

        logger.info(
            "[Pipeline] Initialized pipeline",
            blog_post_id=self.id,
            project_id=self.project_id,
            project_name=self.project.name,
        )

    def update_pipeline_step(self, step_name: str, status: str, error: str = None):
        """Update the status of a specific pipeline step."""
        if not self.pipeline_state:
            self.initialize_pipeline()

        pipeline_state = self.pipeline_state
        if step_name not in pipeline_state["steps"]:
            logger.error(
                "[Pipeline] Invalid step name",
                step_name=step_name,
                blog_post_id=self.id,
            )
            return

        pipeline_state["steps"][step_name]["status"] = status
        if error:
            pipeline_state["steps"][step_name]["error"] = error

        if status == "completed":
            pipeline_state["steps"][step_name]["completed_at"] = timezone.now().isoformat()
            self.pipeline_metadata["steps_completed"] = (
                self.pipeline_metadata.get("steps_completed", 0) + 1
            )

            step_order = [
                "generate_structure",
                "generate_content",
                "preliminary_validation",
                "insert_internal_links",
                "final_validation",
            ]
            current_index = step_order.index(step_name)
            if current_index < len(step_order) - 1:
                pipeline_state["current_step"] = step_order[current_index + 1]
            else:
                pipeline_state["current_step"] = "completed"
                self.pipeline_metadata["completed_at"] = timezone.now().isoformat()

        elif status == "failed":
            pipeline_state["steps"][step_name]["retry_count"] = (
                pipeline_state["steps"][step_name].get("retry_count", 0) + 1
            )
            pipeline_state["steps"][step_name]["failed_at"] = timezone.now().isoformat()

        elif status == "in_progress":
            pipeline_state["current_step"] = step_name
            pipeline_state["steps"][step_name]["started_at"] = timezone.now().isoformat()

        self.pipeline_state = pipeline_state
        self.save(update_fields=["pipeline_state", "pipeline_metadata"])

        logger.info(
            "[Pipeline] Updated step",
            blog_post_id=self.id,
            step_name=step_name,
            status=status,
            error=error,
            retry_count=pipeline_state["steps"][step_name].get("retry_count", 0),
        )

    def get_pipeline_status(self):
        """Return the current pipeline state for API consumption."""
        if not self.pipeline_state:
            return {
                "current_step": None,
                "status": "not_started",
                "steps": {},
                "progress_percentage": 0,
            }

        steps_completed = self.pipeline_metadata.get("steps_completed", 0)
        total_steps = self.pipeline_metadata.get("total_steps", 5)
        progress_percentage = int((steps_completed / total_steps) * 100)

        return {
            "current_step": self.pipeline_state.get("current_step"),
            "status": self.pipeline_state.get("current_step", "pending"),
            "steps": self.pipeline_state.get("steps", {}),
            "progress_percentage": progress_percentage,
            "metadata": self.pipeline_metadata,
        }

    def can_retry_step(self, step_name: str) -> bool:
        """Check if a step can be retried (less than 3 attempts)."""
        if not self.pipeline_state or step_name not in self.pipeline_state["steps"]:
            return False

        retry_count = self.pipeline_state["steps"][step_name].get("retry_count", 0)
        return retry_count < 3


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

    # Embedding for semantic search
    embedding = VectorField(dimensions=1024, default=None, null=True, blank=True)

    # Link usage in blog posts
    always_use = models.BooleanField(
        default=False,
        help_text="When enabled, this page link will always be included in generated blog posts",
    )

    def __str__(self):
        return f"{self.project.name}: {self.title}"

    class Meta:
        unique_together = ("project", "url")
        indexes = [
            HnswIndex(
                name="projectpage_embedding_idx",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def save(self, *args, **kwargs):
        """Override save to validate URL before saving."""
        self.clean()
        super().save(*args, **kwargs)

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
        from core.agents.summarize_page_agent import agent
        from core.utils import get_jina_embedding

        webpage_content = WebPageContent(
            title=self.title,
            description=self.description,
            markdown_content=self.markdown_content,
        )

        analysis_result = run_agent_synchronously(
            agent,
            "Please analyze this web page.",
            deps=webpage_content,
            function_name="analyze_content",
            model_name="ProjectPage",
        )

        self.date_analyzed = timezone.now()

        if self.type == "":
            self.type = analysis_result.output.type

        self.type_ai_guess = analysis_result.output.type_ai_guess
        self.summary = analysis_result.output.summary

        update_fields = [
            "date_analyzed",
            "type",
            "type_ai_guess",
            "summary",
        ]

        if self.title and self.description and self.summary:
            embedding_text = f"{self.title}\n\n{self.description}\n\n{self.summary}"
            embedding = get_jina_embedding(embedding_text)
            if embedding:
                self.embedding = embedding
                update_fields.append("embedding")
                logger.info(
                    "[ProjectPage.analyze_content] Successfully generated and saved embedding",
                    project_page_id=self.id,
                    project_id=self.project_id,
                )
            else:
                logger.warning(
                    "[ProjectPage.analyze_content] Failed to generate embedding",
                    project_page_id=self.id,
                    project_id=self.project_id,
                )
        else:
            logger.info(
                "[ProjectPage.analyze_content] Skipping embedding generation - missing required fields",  # noqa: E501
                project_page_id=self.id,
                project_id=self.project_id,
                has_title=bool(self.title),
                has_description=bool(self.description),
                has_summary=bool(self.summary),
            )

        self.save(update_fields=update_fields)

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

    # Embedding for semantic search
    embedding = VectorField(dimensions=1024, default=None, null=True, blank=True)

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

    # VS comparison blog post content
    blog_post = models.TextField(blank=True, default="")

    class Meta:
        indexes = [
            HnswIndex(
                name="competitor_embedding_idx",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

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

    def populate_name_description(self, model=None):
        from core.utils import get_jina_embedding

        agent = Agent(
            model or get_default_ai_model(),
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
            return f"Content: {ctx.deps.markdown_content}"

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

        self.name = result.output.name
        self.description = result.output.description

        update_fields = ["name", "description"]

        if self.name and self.description and self.summary:
            embedding_text = f"{self.name}\n\n{self.description}\n\n{self.summary}"
            embedding = get_jina_embedding(embedding_text)
            if embedding:
                self.embedding = embedding
                update_fields.append("embedding")
                logger.info(
                    "[Competitor.populate_name_description] Successfully generated and saved embedding",  # noqa: E501
                    competitor_id=self.id,
                    project_id=self.project_id,
                )
            else:
                logger.warning(
                    "[Competitor.populate_name_description] Failed to generate embedding",  # noqa: E501
                    competitor_id=self.id,
                    project_id=self.project_id,
                )
        else:
            logger.info(
                "[Competitor.populate_name_description] Skipping embedding generation - missing required fields",  # noqa: E501
                competitor_id=self.id,
                project_id=self.project_id,
                has_name=bool(self.name),
                has_description=bool(self.description),
                has_summary=bool(self.summary),
            )

        self.save(update_fields=update_fields)

        return True

    def analyze_competitor(self, model=None):
        from core.utils import get_jina_embedding

        agent = Agent(
            model or get_default_ai_model(),
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

        self.competitor_analysis = result.output.competitor_analysis
        self.key_differences = result.output.key_differences
        self.strengths = result.output.strengths
        self.summary = result.output.summary
        self.weaknesses = result.output.weaknesses
        self.opportunities = result.output.opportunities
        self.threats = result.output.threats
        self.key_features = result.output.key_features
        self.key_benefits = result.output.key_benefits
        self.key_drawbacks = result.output.key_drawbacks
        self.links = result.output.links
        self.date_analyzed = timezone.now()

        if self.name and self.description and self.summary:
            embedding_text = f"{self.name}\n\n{self.description}\n\n{self.summary}"
            embedding = get_jina_embedding(embedding_text)
            if embedding:
                self.embedding = embedding
                logger.info(
                    "[Competitor.analyze_competitor] Successfully generated and saved embedding",
                    competitor_id=self.id,
                    project_id=self.project_id,
                )
            else:
                logger.warning(
                    "[Competitor.analyze_competitor] Failed to generate embedding",
                    competitor_id=self.id,
                    project_id=self.project_id,
                )
        else:
            logger.info(
                "[Competitor.analyze_competitor] Skipping embedding generation - missing required fields",  # noqa: E501
                competitor_id=self.id,
                project_id=self.project_id,
                has_name=bool(self.name),
                has_description=bool(self.description),
                has_summary=bool(self.summary),
            )

        self.save()

        return True

    def generate_vs_blog_post(self):
        """
        Generate comparison blog post content using Perplexity Sonar.
        This method uses Perplexity's web search capabilities to research both products.
        """
        from core.agents.competitor_vs_blog_post_agent import agent
        from core.schemas import CompetitorVsPostContext

        title = f"{self.project.name} vs. {self.name}: Which is Better?"

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

        context = CompetitorVsPostContext(
            project_name=self.project.name,
            project_url=self.project.url,
            project_summary=self.project.summary,
            competitor_name=self.name,
            competitor_url=self.url,
            competitor_description=self.description,
            title=title,
            language=self.project.language,
            project_pages=project_pages,
        )

        prompt = "Write a comprehensive comparison blog post. Return ONLY the markdown content for the blog post, nothing else."  # noqa: E501

        result = run_agent_synchronously(
            agent,
            prompt,
            deps=context,
            function_name="generate_vs_blog_post",
            model_name="Competitor",
        )

        self.blog_post = result.output
        self.save(update_fields=["blog_post"])

        return self.blog_post


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

            from core.utils import track_email_sent

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

            for recipient_email in recipient_list:
                track_email_sent(
                    email_address=recipient_email,
                    email_type=EmailType.FEEDBACK_NOTIFICATION,
                    profile=self.profile,
                )


class ReferrerBanner(BaseModel):
    referrer = models.CharField(
        max_length=100,
        unique=True,
        help_text="The referrer code from URL parameter (e.g., 'producthunt' from ?ref=producthunt)",  # noqa: E501
    )
    referrer_printable_name = models.CharField(
        max_length=200,
        help_text="Human-readable name to display in banner (e.g., 'Product Hunt')",
    )
    expiry_date = models.DateTimeField(
        null=True, blank=True, help_text="When to stop showing this banner"
    )
    coupon_code = models.CharField(
        max_length=100, blank=True, help_text="Optional discount coupon code"
    )
    discount_amount = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        help_text="Discount from 0.00 (0%) to 1.00 (100%)",
    )
    is_active = models.BooleanField(
        default=True, help_text="Manually enable/disable banner without deleting it"
    )
    background_color = models.CharField(
        max_length=100,
        default="bg-gradient-to-r from-red-500 to-red-600",
        help_text="Tailwind CSS background color classes (e.g., 'bg-gradient-to-r from-red-500 to-red-600' or 'bg-blue-600')",  # noqa: E501
    )
    text_color = models.CharField(
        max_length=50,
        default="text-white",
        help_text="Tailwind CSS text color class (e.g., 'text-white' or 'text-gray-900')",  # noqa: E501
    )

    def __str__(self):
        return f"{self.referrer_printable_name} ({self.referrer})"

    @property
    def is_expired(self):
        if self.expiry_date is None:
            return False
        return timezone.now() > self.expiry_date

    @property
    def should_display(self):
        return self.is_active and not self.is_expired

    @property
    def discount_percentage(self):
        return int(self.discount_amount * 100)


class EmailSent(BaseModel):
    email_address = models.EmailField(help_text="The recipient email address")
    email_type = models.CharField(
        max_length=50, choices=EmailType.choices, help_text="Type of email sent"
    )
    profile = models.ForeignKey(
        Profile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="emails_sent",
        help_text="Associated user profile, if applicable",
    )

    class Meta:
        verbose_name = "Email Sent"
        verbose_name_plural = "Emails Sent"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email_type} to {self.email_address}"
