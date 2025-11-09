from pydantic_ai import Agent

from core.choices import get_default_ai_model


def create_validate_blog_post_ending_agent(model=None):
    """
    Create an agent to validate if a blog post has a complete, proper ending.

    Args:
        model: Optional AI model to use. Defaults to the default AI model.

    Returns:
        Configured Agent instance that returns a boolean
    """
    agent = Agent(
        model or get_default_ai_model(),
        output_type=bool,
        system_prompt="""
            You are an expert content editor analyzing blog post endings. Your task is to determine
            whether the provided text represents a complete, proper conclusion to a blog post.

            A valid blog post ending should:
            - Complete the final thought or sentence
            - Provide closure to the topic being discussed
            - Feel like a natural conclusion (not abruptly cut off)
            - May include calls-to-action, summaries, or closing remarks

            An invalid ending would be:
            - Cut off mid-sentence
            - Ending abruptly without proper conclusion
            - Incomplete thoughts or paragraphs
            - Missing expected closing elements for the content type

            Analyze the text carefully and provide your assessment. Return True if the ending is valid, False if not.
        """,  # noqa: E501
        retries=2,
        model_settings={"temperature": 0.1},
    )

    return agent
