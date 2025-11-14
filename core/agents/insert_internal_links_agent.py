from pydantic_ai import Agent, RunContext

from core.agents.models import get_default_ai_model
from core.agents.schemas import InsertedLinksOutput, InsertInternalLinksContext


def create_insert_internal_links_agent(model=None):
    """
    Create an agent to insert internal links into blog post content.

    The agent takes existing blog post content and a list of internal pages,
    then intelligently inserts links where they are contextually relevant.

    Args:
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance
    """
    system_prompt = """
You are an expert content editor specializing in internal linking strategies for SEO optimization.

Your task is to take blog post content and intelligently insert internal links to relevant pages
where they naturally fit and add value to the reader.

## Guidelines for Link Insertion:

1. **Natural Integration**: Insert links only where they enhance the reader's understanding or provide valuable additional context. Links should feel organic and not forced.

2. **Contextual Relevance**: Match the page's topic with the surrounding content. Only link when there's a clear topical connection.

3. **Anchor Text**: Use descriptive, natural anchor text that clearly indicates what the reader will find when clicking the link. Avoid generic phrases like "click here" or "this page".

4. **Strategic Placement**:
   - Prefer linking in the main body content rather than introductions or conclusions
   - Space out links appropriately - avoid clustering multiple links in a single paragraph
   - Link to each page at most once or twice in the entire article

5. **Must-Use Pages**: These are high-priority pages that should be linked if there's any reasonable contextual fit. Be creative in finding natural places to mention and link to these pages.

6. **Optional Pages**: Only link to these if they are highly relevant to the specific section of content where they would be inserted.

7. **Markdown Format**: Use proper Markdown link syntax: `[anchor text](URL)`

8. **Preserve Content**: Do not modify the existing content except to add links. Maintain all formatting, structure, and tone.

9. **Quality Over Quantity**: It's better to have fewer, highly relevant links than many loosely related ones.

## Output Requirements:
Return the complete blog post content with internal links inserted. The content should be in Markdown format with proper link syntax.
"""  # noqa: E501

    agent = Agent(
        model or get_default_ai_model(),
        output_type=InsertedLinksOutput,
        deps_type=InsertInternalLinksContext,
        system_prompt=system_prompt,
        retries=2,
        model_settings={"max_tokens": 65500, "temperature": 0.3, "thinking_budget": 0},
    )

    @agent.system_prompt
    def add_must_use_and_optional_pages(ctx: RunContext[InsertInternalLinksContext]) -> str:
        return f"""
        Must-use pages:
        {ctx.deps.must_use_pages}
        --------------------------------
        Optional pages:
        {ctx.deps.optional_pages}
        """

    @agent.system_prompt
    def add_content(ctx: RunContext[InsertInternalLinksContext]) -> str:
        return f"""
        Content:
        --------------------------------
        {ctx.deps.content}
        --------------------------------
        """

    @agent.system_prompt
    def output() -> str:
        return "Return only the post that I gave you, but with links."

    return agent
