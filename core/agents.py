from django.conf import settings
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from core.agent_system_prompts import (
    add_language_specification,
    add_project_details,
    add_project_pages,
    add_target_keywords,
    add_title_details,
    add_webpage_content,
    markdown_lists,
)
from core.choices import AIModel, get_default_ai_model
from core.schemas import (
    BlogPostGenerationContext,
    BlogPostStructure,
    CompetitorVsPostContext,
    CompetitorVsTitleContext,
    ContentFixContext,
    ContentValidationReport,
    InternalLinkContext,
    ProjectDetails,
    ProjectPageDetails,
    TitleSuggestion,
    WebPageContent,
)

########################################################

content_editor_agent = Agent(
    get_default_ai_model(),
    output_type=str,
    deps_type=BlogPostGenerationContext,
    system_prompt="""
    You are an expert content editor.

    Your task is to edit the blog post content based on the requested changes.
    """,
    retries=2,
    model_settings={"temperature": 0.3},
)


@content_editor_agent.system_prompt
def only_return_the_edited_content() -> str:
    return """
        IMPORTANT: Only return the edited content, no other text.
    """


content_editor_agent.system_prompt(add_project_details)
content_editor_agent.system_prompt(add_project_pages)
content_editor_agent.system_prompt(add_title_details)
content_editor_agent.system_prompt(add_language_specification)
content_editor_agent.system_prompt(add_target_keywords)


########################################################

analyze_project_agent = Agent(
    get_default_ai_model(),
    output_type=ProjectDetails,
    deps_type=WebPageContent,
    system_prompt=(
        "You are an expert content analyzer. Based on the content provided, "
        "extract and infer the requested information. Make reasonable inferences based "
        "on available content, context, and industry knowledge."
    ),
    retries=2,
)
analyze_project_agent.system_prompt(add_webpage_content)


########################################################

summarize_page_agent = Agent(
    get_default_ai_model(),
    output_type=ProjectPageDetails,
    deps_type=WebPageContent,
    system_prompt=(
        "You are an expert content summarizer. Based on the web page content provided, "
        "create a concise 2-3 sentence summary that captures the main purpose and key "
        "information of the page. Focus on what the page is about and its main value proposition."
    ),
    retries=2,
    model_settings={"temperature": 0.5},
)
summarize_page_agent.system_prompt(add_webpage_content)


########################################################

competitor_vs_title_agent = Agent(
    OpenAIChatModel(
        AIModel.PERPLEXITY_SONAR,
        provider=OpenAIProvider(
            base_url="https://api.perplexity.ai",
            api_key=settings.PERPLEXITY_API_KEY,
        ),
    ),
    output_type=TitleSuggestion,
    deps_type=CompetitorVsTitleContext,
    system_prompt="""
    You are an expert content strategist specializing in comparison content.

    Your task is to generate a single compelling blog post title that compares
    the user's project with a specific competitor. The title should:

    1. Follow the format: "[Project] vs. [Competitor]: [Compelling Angle]"
    2. Highlight a clear, specific angle for comparison (pricing, features, use cases, etc.)
    3. Be SEO-optimized and search-friendly
    4. Create intrigue and encourage clicks
    5. Be factual and professional (not clickbait)

    Use the latest information available through web search to understand both products
    and create an informed, relevant comparison angle.
    """,
    retries=2,
    model_settings={"temperature": 0.8},
)

competitor_vs_title_agent.system_prompt(markdown_lists)


@competitor_vs_title_agent.system_prompt
def add_competitor_vs_context(ctx):
    context: CompetitorVsTitleContext = ctx.deps
    project = context.project_details
    competitor = context.competitor_details

    return f"""
        Project Details:
        - Name: {project.name}
        - Type: {project.type}
        - Summary: {project.summary}
        - Key Features: {project.key_features}
        - Target Audience: {project.target_audience_summary}

        Competitor Details:
        - Name: {competitor.name}
        - URL: {competitor.url}
        - Description: {competitor.description}

        IMPORTANT: Use web search to research both products and generate
        an informed, specific comparison angle. The title should be based on
        real, up-to-date information about both products.

        Generate only ONE title suggestion with its metadata.
    """


competitor_vs_title_agent.system_prompt(add_language_specification)


########################################################

competitor_vs_blog_post_agent = Agent(
    OpenAIChatModel(
        AIModel.PERPLEXITY_SONAR,
        provider=OpenAIProvider(
            base_url="https://api.perplexity.ai",
            api_key=settings.PERPLEXITY_API_KEY,
        ),
    ),
    output_type=str,
    deps_type=CompetitorVsPostContext,
    system_prompt="""
    You are an expert content writer specializing in product comparisons.

    Create a comprehensive, comparison blog post between two products.
    The post should:

    1. Be well-researched using current information from the web
    2. Include an introduction explaining what both products are
    3. Compare key features, pricing, use cases, pros/cons
    4. Have a slight preference toward the user's project (be subtle)
    5. Include a conclusion helping readers make a decision
    6. Be SEO-optimized with proper headings and structure
    7. Be written in markdown format
    8. Be at least 2000 words
    9. Return ONLY the markdown content, no JSON or structured output

    Important formatting rules:
    - Use ## for main headings (not #)
    - Use ### for subheadings
    - Include bullet points for lists
    - Add a comparison table if relevant
    - Include internal links where appropriate
    """,
    retries=2,
    model_settings={"max_tokens": 8000, "temperature": 0.7},
)

competitor_vs_blog_post_agent.system_prompt(markdown_lists)
competitor_vs_blog_post_agent.system_prompt(add_project_pages)


@competitor_vs_blog_post_agent.system_prompt
def output_format() -> str:
    return """
        IMPORTANT: Return only the text. Don't surround the text with ```markdown or ```.
    """


@competitor_vs_blog_post_agent.system_prompt
def links_insertion() -> str:
    return """
        Instead of leaving reference to links in the text (like this 'sample text[1]'), insert the links into the text in markdown format.
        For example, if the text is 'sample text[1]', the link should be inserted like this: '[sample text](https://www.example.com)'.
    """  # noqa: E501


@competitor_vs_blog_post_agent.system_prompt
def add_competitor_vs_post_context(ctx) -> str:
    context: CompetitorVsPostContext = ctx.deps

    return f"""
        Product 1 (Our Product): {context.project_name}
        URL: {context.project_url}
        Description: {context.project_summary}

        Product 2 (Competitor): {context.competitor_name}
        URL: {context.competitor_url}
        Description: {context.competitor_description}

        Blog Post Title: "{context.title}"

        Language: {context.language}

        Use web search to gather the latest information about both products.
        Research their features, pricing, user reviews, and positioning.
        Create an informative comparison that helps readers make an informed decision.

        Have a slight preference toward {context.project_name} but remain fair and unbiased.
    """


########################################################
# Pipeline Agents
########################################################

blog_structure_agent = Agent(
    get_default_ai_model(),
    output_type=BlogPostStructure,
    deps_type=BlogPostGenerationContext,
    system_prompt="""
    You are an expert content strategist and SEO specialist.

    Your task is to create a comprehensive, well-structured outline for a blog post.
    Think deeply about:

    1. **Logical Flow**: How should information be presented for maximum clarity and impact?
    2. **SEO Optimization**: What headings and structure will rank well in search engines?
    3. **User Intent**: What questions does the reader have, and in what order should they be answered?
    4. **Comprehensiveness**: What topics must be covered for this to be a complete resource?
    5. **Readability**: How can we break down complex topics into digestible sections?

    Consider the project details, title suggestion, and available project pages when creating the structure.
    The structure should be detailed enough that a writer can follow it to create excellent content.

    Important guidelines:
    - Use H2 (level 2) for main sections
    - Use H3 (level 3) for subsections within main sections
    - Aim for 5-8 main sections (H2) for a comprehensive post
    - Each section should have 3-5 key points to cover
    - Target 2000-3000 total words for the post
    - Include specific guidance for introduction and conclusion
    """,  # noqa: E501
    retries=2,
    model_settings={"temperature": 0.7},
)

blog_structure_agent.system_prompt(add_project_details)
blog_structure_agent.system_prompt(add_project_pages)
blog_structure_agent.system_prompt(add_title_details)
blog_structure_agent.system_prompt(add_language_specification)
blog_structure_agent.system_prompt(add_target_keywords)


########################################################

internal_links_agent = Agent(
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


@internal_links_agent.system_prompt
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


########################################################

content_validator_agent = Agent(
    get_default_ai_model(),
    output_type=ContentValidationReport,
    deps_type=str,
    system_prompt="""
    You are an expert content quality auditor.

    Your task is to thoroughly review blog post content and identify any issues that would
    prevent it from being published successfully.

    Check for these specific issues:

    1. **Content Length**: Is the content at least 3000 characters? If not, it's too short.

    2. **Placeholders**: Look for any placeholder text like:
       - [IMAGE], [LINK], [TODO], [TBD]
       - "Insert X here"
       - "Add details about..."
       - Bracketed suggestions

    3. **Valid Ending**: Does the content have a proper conclusion?
       - Should not end abruptly mid-sentence
       - Should not end with an incomplete thought
       - Should have a concluding section or final thoughts

    4. **Header Start**: Does the content start with a markdown header (#, ##, ###)?
       - Content should start with plain text (introduction)
       - Not start with a heading

    5. **Broken Markdown**: Check for markdown syntax errors:
       - Unclosed brackets or parentheses
       - Broken links
       - Malformed lists
       - Invalid heading syntax

    Be thorough but fair. If something is a minor stylistic issue, don't flag it as critical.
    Focus on issues that would prevent publication or significantly harm content quality.
    """,
    retries=1,
    model_settings={"temperature": 0.2},
)


########################################################

content_fixer_agent = Agent(
    get_default_ai_model(),
    output_type=str,
    deps_type=ContentFixContext,
    system_prompt="""
    You are an expert content editor specialized in fixing specific content issues.

    Your task is to fix the identified validation issues while preserving the quality
    and intent of the original content.

    Guidelines:
    - Fix ONLY the issues mentioned in the validation report
    - Maintain the original style, tone, and voice
    - Do not rewrite sections that don't need fixing
    - Be surgical - make targeted fixes, not wholesale changes
    - Ensure all fixes maintain content quality and coherence

    IMPORTANT: Return ONLY the fixed content, no additional commentary or explanation.
    """,
    retries=2,
    model_settings={"temperature": 0.4},
)

content_fixer_agent.system_prompt(add_project_details)
content_fixer_agent.system_prompt(add_title_details)


@content_fixer_agent.system_prompt
def add_fix_context(ctx) -> str:
    context: ContentFixContext = ctx.deps

    issues_text = "\n".join(
        [
            f"- {issue.issue_type}: {issue.details}"
            + (f" (Location: {issue.location})" if issue.location else "")
            for issue in context.validation_report.issues
        ]
    )

    return f"""
    Content to Fix:
    {context.content}

    Issues Found:
    {issues_text}

    Please fix these issues while maintaining the original content's quality and intent.
    """
