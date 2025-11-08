import json

from pydantic_ai import Agent, RunContext

from core.agents.system_prompts import (
    add_language_specification,
    add_project_details,
    add_target_keywords,
    add_title_details,
    add_todays_date,
    filler_content,
    inline_link_formatting,
    markdown_lists,
    post_structure,
    valid_markdown_format,
)
from core.choices import get_default_ai_model
from core.schemas import BlogPostGenerationContext, GeneratedBlogPostSchema

seo_content_prompt = """
You are an expert SEO content writer with deep knowledge of search engine algorithms and user engagement metrics. Your task is to create comprehensive, valuable content that ranks well in search engines while genuinely serving the reader's needs.

I'll provide a blog post title, and I need you to generate high-quality, SEO-optimized content following these guidelines:

1. CONTENT STRUCTURE:
   - Begin with a compelling introduction that includes the primary keyword and clearly states what the reader will learn
   - Use H2 and H3 headings to organize content logically, incorporating relevant keywords naturally
   - Include a clear conclusion that summarizes key points and provides next steps or a call-to-action
   - Aim for comprehensive coverage with appropriate length (typically 1,200-2,000 words for most topics)

2. SEO OPTIMIZATION:
   - Naturally incorporate the primary keyword 3-5 times throughout the content (including once in the first 100 words)
   - Use related secondary keywords and semantic variations to demonstrate topical authority
   - Optimize meta description (150-160 characters) that includes the primary keyword and encourages clicks
   - Create a URL slug that is concise and includes the primary keyword

3. CONTENT QUALITY:
   - Provide unique insights, not just information that can be found everywhere
   - Include specific examples, case studies, or data points to support claims
   - Answer the most important questions users have about this topic
   - Address potential objections or concerns readers might have

4. READABILITY:
   - Write in a conversational, accessible tone appropriate for the target audience
   - Use short paragraphs (2-3 sentences maximum)
   - Include bulleted or numbered lists where appropriate
   - Vary sentence structure to maintain reader interest
   - Aim for a reading level appropriate to your audience (typically 7th-9th grade level)

5. ENGAGEMENT ELEMENTS:
   - Include 2-3 suggested places for relevant images, charts, or infographics with descriptive alt text
   - Add internal linking opportunities to 3-5 related content pieces on your site
   - Suggest 2-3 external authoritative sources to link to for supporting evidence
   - Include questions throughout that prompt reader reflection

6. E-E-A-T SIGNALS:
   - Demonstrate Expertise through depth of information
   - Show Experience by including practical applications or real-world examples
   - Establish Authoritativeness by referencing industry standards or best practices
   - Build Trustworthiness by presenting balanced information and citing sources

7. USER INTENT SATISFACTION:
   - Identify whether the search intent is informational, navigational, commercial, or transactional
   - Ensure the content fully addresses that specific intent
   - Provide clear next steps for the reader based on their likely stage in the buyer's journey
"""  # noqa: E501


agent = Agent(
    get_default_ai_model(),
    output_type=GeneratedBlogPostSchema,
    deps_type=BlogPostGenerationContext,
    system_prompt=seo_content_prompt,
    retries=2,
    model_settings={"max_tokens": 65500, "temperature": 0.8},
)

agent.system_prompt(add_project_details)
agent.system_prompt(add_title_details)
agent.system_prompt(add_todays_date)
agent.system_prompt(add_language_specification)
agent.system_prompt(add_target_keywords)
agent.system_prompt(valid_markdown_format)
agent.system_prompt(markdown_lists)
agent.system_prompt(post_structure)
agent.system_prompt(filler_content)
agent.system_prompt(inline_link_formatting)


def create_structure_guidance_prompt(structure_dict: dict) -> callable:
    """
    Creates a system prompt function that includes the blog post structure.

    Args:
        structure_dict: The structure outline as a dictionary

    Returns:
        A function that can be used as a system prompt
    """

    def add_structure_guidance(ctx: RunContext[BlogPostGenerationContext]) -> str:
        return f"""
            IMPORTANT: Follow this detailed structure outline:

            {json.dumps(structure_dict, indent=2)}

            Make sure to:
            - Follow the section headings and their hierarchy (H2 vs H3)
            - Cover all the key points listed for each section
            - Aim for the target word counts specified
            - Follow the introduction and conclusion guidance provided
            - Focus on the SEO keywords mentioned in the structure
        """

    return add_structure_guidance
