from django.utils import timezone
from pydantic_ai import RunContext

from core.agents.schemas import BlogPostGenerationContext, WebPageContent


def add_todays_date() -> str:
    return f"Today's Date: {timezone.now().strftime('%Y-%m-%d')}"


def valid_markdown_format() -> str:
    return """
        IMPORTANT: Generate the content in valid markdown format.
        Make sure the content is formatted correctly with:
          - headings
          - paragraphs
          - lists
          - links
    """


def post_structure() -> str:
    return """
        - Don't start with a title, header or a subheader (#, ##, ###). Instead start with a plain text as intro.
        - Use '##' (h2 headers) for sections of the post where necessary.
        - Don't use 3rd levle subheaders (###) or deeper. That should not be necessary for the post.
    """  # noqa: E501


def markdown_lists() -> str:
    return """
        - Add an empty line before the first item in the list.
        - Use lists for bullet points where necessary.
        - Use numbered lists for steps or instructions.
        - Use nested lists for sub-points.
    """  # noqa: E501


def filler_content() -> str:
    return """
        - Do not add content that needs to be filled in later.
        - No placeholders either. This means no:
          - Image Suggestion: [Image]
          - Link Suggestion: [Link]
          ...
      """


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


def add_project_pages(ctx: RunContext) -> str:
    """
    Generic function to add project pages to any context that has a project_pages attribute.
    Works with BlogPostGenerationContext, CompetitorVsPostContext, and any other context
    that includes project pages.
    """
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
        title.suggested_meta_description if title.suggested_meta_description else "None specified"
    }
    """


def add_language_specification(ctx: RunContext[BlogPostGenerationContext]) -> str:
    return f"""
        IMPORTANT: Generate the content in {ctx.deps.project_details.language} language.
        Make sure the content is grammatically correct and culturally appropriate for
        {ctx.deps.project_details.language}-speaking audiences.
    """


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


def outline_generation_guidelines() -> str:
    """Guidelines for creating structured blog post outlines."""
    return """
        OUTLINE GENERATION GUIDELINES

        Your task is to create a logical, hierarchical outline for the blog post.

        KEY PRINCIPLES:
        - Create meaningful, relevant section titles that flow logically
        - Keep sections concise but comprehensive
        - Use the provided keywords only as reference, not inside the outline text
        - Ensure the outline covers the topic thoroughly
        - Structure should support natural keyword distribution in the final article
        - Each section should have a clear purpose and contribute to the overall narrative

        STRUCTURE REQUIREMENTS:
        - Introduction summary: What hook/context to establish (2-3 sentences)
        - Main sections: 4-7 major sections with clear, descriptive titles
        - Each main section can have 0-4 subsections/key points
        - Conclusion summary: How to wrap up and provide next steps (2-3 sentences)

        AVOID:
        - Generic section titles like "Introduction" or "Conclusion"
        - Keyword stuffing in section titles
        - Overly complex nested structures
        - Filler sections that don't add value
        - Vague or ambiguous section names
    """


def article_from_outline_guidelines() -> str:
    """Guidelines for drafting articles from outlines with proper keyword distribution."""
    return """
        ARTICLE DRAFTING GUIDELINES

        Your task is to expand the provided outline into a complete, well-structured article.

        STRUCTURAL REQUIREMENTS:
        - Each section in the outline MUST become a heading (## H2) followed by detailed content
        - The article must strictly follow the outline structure
        - Start with plain text introduction (no heading)
        - Use ## (H2) for main sections only
        - Do NOT use ### (H3) or deeper headings

        KEYWORD DISTRIBUTION:
        - The provided keywords must be distributed naturally throughout the ENTIRE article
        - Distribution should be even: introduction, body sections, and conclusion
        - Ensure no single section feels overloaded with keywords
        - Maintain natural flow and readability at all times
        - NEVER sacrifice readability for keyword placement
        - Keywords should blend seamlessly into the content

        CONTENT QUALITY:
        - Every paragraph must add value - avoid filler content
        - Maintain informative, coherent, and easy-to-read tone
        - Do not repeat the same paragraph or phrase
        - Keep formatting clean and consistently structured
        - Ensure machine-friendly output that passes Django parsing cleanly

        WHAT TO AVOID:
        - Keyword stuffing or unnatural keyword placement
        - Inventing specific statistics or data unless provided
        - Placeholders like [Image], [Link], etc.
        - Starting with a heading
        - Repeating content across sections
        - Generic filler phrases
    """


def add_outline_context(ctx: RunContext) -> str:
    """Add the outline to the context for article drafting."""
    if hasattr(ctx.deps, 'outline') and ctx.deps.outline:
        outline = ctx.deps.outline
        outline_text = f"""
        OUTLINE TO FOLLOW:

        Introduction Focus:
        {outline.introduction_summary}

        Main Sections:
        """

        for index, section in enumerate(outline.main_sections, 1):
            outline_text += f"\n{index}. {section.section_title}"
            if section.subsections:
                for subsection in section.subsections:
                    outline_text += f"\n   - {subsection}"

        outline_text += f"""

        Conclusion Focus:
        {outline.conclusion_summary}

        IMPORTANT: Your article must strictly follow this outline structure. Each section above must become a ## heading in your article, followed by comprehensive content that addresses the section's focus.
        """  # noqa: E501

        return outline_text
    return ""


def add_target_keywords_for_outline(ctx: RunContext) -> str:
    """Add keywords context for outline generation."""
    if hasattr(ctx.deps, 'target_keywords') and ctx.deps.target_keywords:
        keywords_list = ", ".join(ctx.deps.target_keywords)
        return f"""
            REFERENCE KEYWORDS (for outline planning only):
            {keywords_list}

            Note: These keywords are for your reference. Do NOT include them in the outline section titles.
            They will be naturally distributed when the article is written from this outline.
        """  # noqa: E501
    return ""


def add_target_keywords_for_article(ctx: RunContext) -> str:
    """Add keywords context for article drafting with distribution requirements."""
    if hasattr(ctx.deps, 'target_keywords') and ctx.deps.target_keywords:
        keywords_list = ", ".join(ctx.deps.target_keywords)
        return f"""
            KEYWORDS TO DISTRIBUTE NATURALLY:
            {keywords_list}

            DISTRIBUTION REQUIREMENTS:
            - These keywords must appear throughout the ENTIRE article
            - Start distributing from the introduction
            - Continue through all main sections
            - Include in the conclusion
            - Ensure EVEN distribution - no section should have too many or too few
            - Every keyword should appear multiple times across different sections
            - Maintain natural flow - never force keywords where they don't fit
            - Blend keywords seamlessly into sentences
        """  # noqa: E501
    return ""


def add_webpage_content(ctx: RunContext[WebPageContent]) -> str:
    return (
        "Web page content:"
        f"Title: {ctx.deps.title}"
        f"Description: {ctx.deps.description}"
        f"Content: {ctx.deps.markdown_content}"
    )
