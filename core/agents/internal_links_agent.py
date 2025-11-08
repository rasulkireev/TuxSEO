from pydantic_ai import Agent

from core.agents.system_prompts import inline_link_formatting
from core.choices import get_default_ai_model
from core.schemas import InternalLinkContext

agent = Agent(
    get_default_ai_model(),
    output_type=str,
    deps_type=InternalLinkContext,
    system_prompt="""
    You are an expert at strategically inserting internal links into content.

    Your task is to identify relevant places in the blog post content where internal links
    to the project's pages would add value for readers and improve SEO.

    Guidelines:
    - Only insert links where they are contextually relevant and add value
    - Use natural anchor text that fits the flow of the content
    - For "always_use" pages, you MUST find appropriate places to link them
    - For optional pages, only link if they truly enhance the content
    - Avoid over-linking (max 1 link per 200 words as a general rule)
    - Vary your anchor text - don't use the same text repeatedly
    - Link early in the content when possible, but prioritize natural placement

    Return the content with internal links inserted in markdown format: [anchor text](url)

    IMPORTANT: Return ONLY the modified content, no additional commentary or explanation.
    """,
    retries=2,
    model_settings={"temperature": 0.3},
)


agent.system_prompt(inline_link_formatting)


@agent.system_prompt
def add_internal_link_context(ctx) -> str:
    context: InternalLinkContext = ctx.deps

    always_use_pages = [page for page in context.available_pages if page.always_use]
    optional_pages = [page for page in context.available_pages if not page.always_use]

    instruction = f"""
    Current Content:
    {context.content}

    """

    if always_use_pages:
        instruction += """
        REQUIRED PAGES TO LINK (Must be included):
        """
        for page in always_use_pages:
            instruction += f"""
            - Title: {page.title}
            - URL: {page.url}
            - Description: {page.description}

            """

    if optional_pages:
        instruction += """
        OPTIONAL PAGES (Link only if contextually relevant):
        """
        for page in optional_pages:
            instruction += f"""
            - Title: {page.title}
            - URL: {page.url}
            - Description: {page.description}

            """

    return instruction
