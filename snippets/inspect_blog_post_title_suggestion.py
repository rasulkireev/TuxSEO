from core.models import (
    BlogPostTitleSuggestion,
    GeneratedBlogPost,
    GeneratedBlogPostResearchLink,
    GeneratedBlogPostResearchQuestion,
    GeneratedBlogPostSection,
)
from core.utils import get_relevant_external_pages_for_blog_post


def format_heading(text: str) -> str:
    return f"\n{'=' * 16} {text} {'=' * 16}\n"


def format_subheading(text: str) -> str:
    return f"\n{'-' * 10} {text} {'-' * 10}\n"


blog_post_title_suggestion_id_raw = input("BlogPostTitleSuggestion id: ").strip()
blog_post_title_suggestion_id = int(blog_post_title_suggestion_id_raw)

title_suggestion = (
    BlogPostTitleSuggestion.objects.select_related("project")
    .filter(id=blog_post_title_suggestion_id)
    .first()
)

if not title_suggestion:
    raise ValueError(f"BlogPostTitleSuggestion not found: {blog_post_title_suggestion_id}")

project = title_suggestion.project

print(format_heading("TITLE SUGGESTION"))
print(f"id: {title_suggestion.id}")
print(f"project_id: {title_suggestion.project_id}")
print(f"title: {title_suggestion.title}")
print(f"content_type: {title_suggestion.content_type}")
print(f"category: {title_suggestion.category}")
print(f"description: {title_suggestion.description}")
print(f"prompt: {title_suggestion.prompt}")
print(f"target_keywords: {title_suggestion.target_keywords or []}")
print(f"suggested_meta_description: {title_suggestion.suggested_meta_description}")
print(f"user_score: {title_suggestion.user_score}")
print(f"archived: {title_suggestion.archived}")

print(format_heading("PROJECT"))
if not project:
    print("No project associated")
else:
    print(f"id: {project.id}")
    print(f"name: {project.name}")
    print(f"type: {project.type}")
    print(f"language: {project.language}")
    print(f"location: {project.location}")
    print(f"summary: {project.summary}")
    print(f"blog_theme: {project.blog_theme}")
    print(f"founders: {project.founders}")
    print(f"key_features: {project.key_features}")
    print(f"target_audience_summary: {project.target_audience_summary}")
    print(f"pain_points: {project.pain_points}")
    print(f"product_usage: {project.product_usage}")
    print(f"proposed_keywords: {project.proposed_keywords}")
    print(f"links: {project.links}")

print(format_heading("DERIVED INPUTS"))
keywords_to_use = title_suggestion.get_blog_post_keywords()
print(f"keywords_to_use ({len(keywords_to_use)}): {keywords_to_use}")

try:
    internal_links = title_suggestion.get_internal_links(max_pages=2)
except Exception as error:
    internal_links = []
    print(f"get_internal_links error: {error}")

print(f"internal_links ({len(internal_links)}):")
for project_page in internal_links:
    print(
        f"- [{project_page.id}] {project_page.title} | {project_page.url} | always_use={project_page.always_use}"  # noqa: E501
    )

try:
    external_links = list(
        get_relevant_external_pages_for_blog_post(
            meta_description=title_suggestion.suggested_meta_description or "",
            exclude_project=title_suggestion.project,
            max_pages=3,
        )
    )
except Exception as error:
    external_links = []
    print(f"get_relevant_external_pages_for_blog_post error: {error}")

print(f"external_links ({len(external_links)}):")
for project_page in external_links:
    print(
        f"- [{project_page.id}] {project_page.title} | {project_page.url} | "
        f"project_id={project_page.project_id} always_use={project_page.always_use}"
    )

generated_blog_posts = (
    GeneratedBlogPost.objects.filter(title_suggestion=title_suggestion)
    .select_related("project", "title_suggestion")
    .order_by("-id")
)

print(format_heading("GENERATED BLOG POSTS"))
print(f"count: {generated_blog_posts.count()}")

for blog_post in generated_blog_posts:
    print(format_subheading(f"GeneratedBlogPost {blog_post.id}"))
    print(f"id: {blog_post.id}")
    print(f"project_id: {blog_post.project_id}")
    print(f"title_suggestion_id: {blog_post.title_suggestion_id}")
    print(f"title: {blog_post.title}")
    print(f"description: {blog_post.description}")
    print(f"slug: {blog_post.slug}")
    print(f"tags: {blog_post.tags}")
    print(f"posted: {blog_post.posted}")
    print(f"date_posted: {blog_post.date_posted}")
    print(f"content_length: {len(blog_post.content or '')}")

    sections = GeneratedBlogPostSection.objects.filter(blog_post=blog_post).order_by("order", "id")
    print(format_subheading(f"Sections ({sections.count()})"))

    for section in sections:
        print(
            f"[{section.order}] section_id={section.id} title={section.title} content_length={len(section.content or '')}"  # noqa: E501
        )

        section_questions = GeneratedBlogPostResearchQuestion.objects.filter(
            section=section
        ).order_by("id")
        print(f"  research_questions ({section_questions.count()}):")
        for research_question in section_questions:
            print(f"  - [{research_question.id}] {research_question.question}")

            question_links = (
                GeneratedBlogPostResearchLink.objects.filter(research_question=research_question)
                .order_by("id")
                .values(
                    "id",
                    "url",
                    "title",
                    "author",
                    "published_date",
                    "date_scraped",
                    "date_analyzed",
                )
            )
            question_links_list = list(question_links)
            print(f"    links ({len(question_links_list)}):")
            for research_link in question_links_list:
                print(
                    f"    - [{research_link['id']}] {research_link['title']} | {research_link['url']} | "  # noqa: E501
                    f"author={research_link['author']} published_date={research_link['published_date']} "  # noqa: E501
                    f"date_scraped={research_link['date_scraped']} date_analyzed={research_link['date_analyzed']}"  # noqa: E501
                )

    blog_post_questions = GeneratedBlogPostResearchQuestion.objects.filter(
        blog_post=blog_post,
        section__isnull=True,
    ).order_by("id")
    if blog_post_questions.exists():
        print(format_subheading(f"Blog-level research questions ({blog_post_questions.count()})"))
        for research_question in blog_post_questions:
            print(f"- [{research_question.id}] {research_question.question}")

print(format_heading("DONE"))
