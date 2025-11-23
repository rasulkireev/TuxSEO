from pydantic_ai import Agent

from core.agents.schemas import LinkInsertionContext
from core.choices import get_default_ai_model


def create_insert_links_agent(model=None):
    """
    Create an agent to insert links into blog post content organically.

    Args:
        model: Optional AI model to use. Defaults to GPT-4o.

    Returns:
        Configured Agent instance
    """
    if model is None:
        model = get_default_ai_model()

    agent = Agent(
        model,
        output_type=str,
        deps_type=LinkInsertionContext,
        system_prompt="""
        You are an expert content editor specializing in organic link insertion.

        Your task is to insert links from the provided project pages into the blog post content.
        The links should be inserted naturally and organically where they add value to the reader.

        CRITICAL RULES:
        1. DO NOT edit, rewrite, or change ANY of the existing blog post content
        2. DO NOT add new paragraphs or sentences
        3. DO NOT remove any existing content
        4. ONLY insert markdown links into existing text where appropriate
        5. Insert links by wrapping relevant existing text with markdown link syntax: [text](url)
        6. Each project page should be linked AT MOST ONCE in the entire post
        7. Only insert links where they are contextually relevant and add value
        8. Return the EXACT same blog post with only the links inserted
        9. Return ONLY the markdown content, no JSON or structured output

        HANDLING EXISTING REFERENCE LINKS:
        - If the blog post contains reference-style links like "text [Source, Year](link)" or "text [1](link)"
        - Convert them to inline links by integrating them naturally into the text
        - Example: "This is a fact [Source, 2024](https://example.com)" → "This is [a fact](https://example.com)"
        - Example: "According to research [1](https://example.com)" → "According to [research](https://example.com)"
        - DO NOT keep the reference format like [Source, Year] or [1], [2], etc.
        - Make the links flow naturally within the sentence

        Link Insertion Guidelines:
        - Look for phrases or sentences where linking would naturally enhance the content
        - Link relevant keywords or phrases that relate to the project page content
        - Ensure the anchor text is descriptive and natural
        - Distribute links throughout the post (not all in one section)
        - Prefer linking in body paragraphs over headers or introduction

        Example of what TO DO:
        Original: "This feature helps you track your website performance."
        With Link: "This feature helps you [track your website performance](https://example.com/analytics)."

        Converting Reference Links:
        Original: "Machine learning improves accuracy [Study, 2024](https://example.com)."
        Converted: "Machine learning [improves accuracy](https://example.com)."

        Example of what NOT TO DO:
        - DO NOT add: "Learn more about our features [here](url)" if that sentence wasn't there
        - DO NOT change: "This is great" to "This is amazing" even with a link
        - DO NOT restructure or reformat the content
        - DO NOT keep reference-style citations like [Source, Year](url) or [1](url)
        """,  # noqa: E501
        retries=2,
        model_settings={"max_tokens": 65500, "temperature": 0.1},
    )

    @agent.system_prompt
    def add_link_insertion_context(ctx) -> str:
        context: LinkInsertionContext = ctx.deps

        pages_info = ""
        for index, page in enumerate(context.project_pages, start=1):
            pages_info += f"""
            Page {index}:
            - URL: {page.url}
            - Title: {page.title}
            - Description: {page.description}
            - Summary: {page.summary}
            """

        return f"""
            PROJECT PAGES TO LINK:
            {pages_info}

            BLOG POST CONTENT TO INSERT LINKS INTO:
            {context.blog_post_content}

            INSTRUCTIONS:
            1. Insert links from the project pages above organically into the blog post
            2. Convert any existing reference-style links (like "text [Source, Year](url)" or "text [1](url)") to natural inline links (like "[text](url)")
            3. Do not change the content, only insert/convert links
            4. Return only the markdown content with links properly inserted
        """  # noqa: E501

    return agent
