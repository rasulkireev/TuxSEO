from urllib.request import urlopen

import replicate
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models

from core.agents import (
    create_insert_links_agent,
)
from core.agents.schemas import (
    GeneratedBlogPostSchema,
    LinkInsertionContext,
    ProjectPageContext,
)
from core.base_models import BaseModel
from core.choices import (
    OGImageStyle,
)
from core.models import AutoSubmissionSetting, BlogPostTitleSuggestion, Project
from core.utils import (
    get_og_image_prompt,
    get_relevant_external_pages_for_blog_post,
)
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


class GeneratedBlogPost(BaseModel):
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="generated_blog_posts",
    )
    title_suggestion = models.ForeignKey(
        BlogPostTitleSuggestion,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="generated_blog_posts",
    )

    # Final Output Items
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=250)
    tags = models.TextField()
    content = models.TextField()
    icon = models.ImageField(upload_to="generated_blog_post_icons/", blank=True)
    image = models.ImageField(upload_to="generated_blog_post_images/", blank=True)

    # Preparation
    # GeneratedBlogPostSection model

    # Other
    posted = models.BooleanField(default=False)
    date_posted = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.project.name}: {self.title}"

    @classmethod
    def blog_post_structure_rules(cls):
        return """
        - Use markdown.
        - Start with the title as h1 (#). Do no include any other metadata (description, slug, etc.)
        - Then do and intro, starting with `## Introduction`, then a paragraph of text.
        - Continue with h2 (##) topics as you see fit.
        - Do not go deeper than h2 (##) for post structure.
        - Never inlcude placeholder items (insert image here, link suggestions, etc.)
        - Do not have `References` section, insert all the links into the post directly, organically.
        - Do not include a call to action paragraph at the end of the post.
        - Finish the post with a conclusion.
        - Instead of using links as a reference, try to insert them into the post directly, organically.
        """  # noqa: E501

    @property
    def generated_blog_post_schema(self):
        return GeneratedBlogPostSchema(
            description=self.description,
            slug=self.slug,
            tags=self.tags,
            content=self.content,
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

    def generate_og_image(self) -> tuple[bool, str]:
        """
        Generate an Open Graph image for a blog post using Replicate flux-schnell model.

        Args:
            generated_post: The GeneratedBlogPost instance to generate an image for
            replicate_api_token: Replicate API token for authentication

        Returns:
            A tuple of (success: bool, message: str)
        """

        if not settings.REPLICATE_API_TOKEN:
            logger.error(
                "[GenerateOGImage] Replicate API token not configured",
                blog_post_id=self.id,
                project_id=self.project_id,
            )
            return False, "Replicate API token not configured"

        if self.image:
            logger.info(
                "[GenerateOGImage] Image already exists for blog post",
                blog_post_id=self.id,
                project_id=self.project_id,
            )
            return True, f"Image already exists for blog post {self.id}"

        try:
            blog_post_category = (
                self.title_suggestion.category if self.title_suggestion.category else "technology"
            )

            project_og_style = self.project.og_image_style or OGImageStyle.MODERN_GRADIENT
            prompt = get_og_image_prompt(project_og_style, blog_post_category)

            logger.info(
                "[GenerateOGImage] Starting image generation",
                blog_post_id=self.id,
                project_id=self.project_id,
                category=blog_post_category,
                og_style=project_og_style,
                prompt=prompt,
            )

            replicate_client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)

            output = replicate_client.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": prompt,
                    "aspect_ratio": "16:9",
                    "output_format": "png",
                    "output_quality": 90,
                },
            )

            if not output:
                logger.error(
                    "[GenerateOGImage] No output from Replicate",
                    blog_post_id=self.id,
                    project_id=self.project_id,
                )
                return False, f"Failed to generate image for blog post {self.id}"

            file_output = output[0] if isinstance(output, list) else output
            image_url = str(file_output)

            logger.info(
                "[GenerateOGImage] Image generated successfully",
                blog_post_id=self.id,
                project_id=self.project_id,
                image_url=image_url,
            )

            image_response = urlopen(image_url)
            image_content = ContentFile(image_response.read())

            filename = f"og-image-{self.id}.png"
            self.image.save(filename, image_content, save=True)

            logger.info(
                "[GenerateOGImage] Image saved to blog post",
                blog_post_id=self.id,
                project_id=self.project_id,
                saved_url=self.image.url,
            )

            return True, f"Successfully generated and saved OG image for blog post {self.id}"

        except replicate.exceptions.ReplicateError as replicate_error:
            logger.error(
                "[GenerateOGImage] Replicate API error",
                error=str(replicate_error),
                exc_info=True,
                blog_post_id=self.id,
                project_id=self.project_id,
            )
            return False, f"Replicate API error: {str(replicate_error)}"
        except Exception as error:
            logger.error(
                "[GenerateOGImage] Unexpected error during image generation",
                error=str(error),
                exc_info=True,
                blog_post_id=self.id,
                project_id=self.project_id,
            )
            return False, f"Unexpected error: {str(error)}"

    def insert_links_into_post(self, max_pages=4, max_external_pages=3):
        """
        Insert links from project pages into the blog post content organically.
        Uses PydanticAI to intelligently place links without modifying the content.

        Args:
            max_pages: Maximum number of internal project pages to use for linking (default: 4)
            max_external_pages: Maximum number of external project pages to use for linking (default: 3)

        Returns:
            str: The blog post content with links inserted
        """  # noqa: E501
        from core.utils import (
            get_relevant_pages_for_blog_post,
            run_agent_synchronously,
        )

        if not self.title_suggestion:
            logger.warning(
                "[InsertLinksIntoPost] No title suggestion found for blog post",
                blog_post_id=self.id,
                project_id=self.project_id,
            )
            return self.content

        # Get internal project pages
        manually_selected_project_pages = list(self.project.project_pages.filter(always_use=True))
        relevant_project_pages = list(
            get_relevant_pages_for_blog_post(
                self.project,
                self.title_suggestion.suggested_meta_description,
                max_pages=max_pages,
            )
        )

        all_project_pages = manually_selected_project_pages + relevant_project_pages

        # Get external project pages if link exchange is enabled
        external_project_pages = []
        if self.project.particiate_in_link_exchange:
            external_project_pages = list(
                get_relevant_external_pages_for_blog_post(
                    meta_description=self.title_suggestion.suggested_meta_description,
                    exclude_project=self.project,
                    max_pages=max_external_pages,
                )
            )
            # Filter to only include pages from projects that also participate in link exchange
            external_project_pages = [
                page for page in external_project_pages if page.project.particiate_in_link_exchange
            ]

        all_pages_to_link = all_project_pages + external_project_pages

        if not all_pages_to_link:
            logger.info(
                "[InsertLinksIntoPost] No pages found for link insertion",
                blog_post_id=self.id,
                project_id=self.project_id,
            )
            return self.content

        project_page_contexts = [
            ProjectPageContext(
                url=page.url,
                title=page.title,
                description=page.description,
                summary=page.summary,
            )
            for page in all_pages_to_link
        ]

        # Extract URLs for logging
        urls_to_insert = [page.url for page in all_pages_to_link]
        internal_urls = [page.url for page in all_project_pages]
        external_urls = [page.url for page in external_project_pages]

        link_insertion_context = LinkInsertionContext(
            blog_post_content=self.content,
            project_pages=project_page_contexts,
        )

        insert_links_agent = create_insert_links_agent()

        prompt = "Insert the provided project page links into the blog post content organically. Do not modify the existing content, only add links where appropriate."  # noqa: E501

        logger.info(
            "[InsertLinksIntoPost] Running link insertion agent",
            blog_post_id=self.id,
            project_id=self.project_id,
            num_total_pages=len(project_page_contexts),
            num_internal_pages=len(all_project_pages),
            num_external_pages=len(external_project_pages),
            num_always_use_pages=len(manually_selected_project_pages),
            participate_in_link_exchange=self.project.particiate_in_link_exchange,
            urls_to_insert=urls_to_insert,
            internal_urls=internal_urls,
            external_urls=external_urls,
        )

        result = run_agent_synchronously(
            insert_links_agent,
            prompt,
            deps=link_insertion_context,
            function_name="insert_links_into_post",
            model_name="GeneratedBlogPost",
        )

        content_with_links = result.output

        self.content = content_with_links
        self.save(update_fields=["content"])

        logger.info(
            "[InsertLinksIntoPost] Links inserted successfully",
            blog_post_id=self.id,
            project_id=self.project_id,
        )

        return content_with_links
