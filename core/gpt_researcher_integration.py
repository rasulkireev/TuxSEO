import asyncio

from django.conf import settings
from gpt_researcher import GPTResearcher

from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


async def research_with_gpt_researcher(query: str, report_type: str = "research_report") -> str:
    """
    Use GPT Researcher to conduct research on a topic and return detailed report.

    Args:
        query: The research question or topic
        report_type: Type of report to generate (default: "research_report")

    Returns:
        String containing the research report
    """
    try:
        researcher = GPTResearcher(query=query, report_type=report_type)
        await researcher.conduct_research()
        report = await researcher.write_report()
        return report
    except Exception as error:
        logger.error(
            "[GPT Researcher] Error conducting research",
            error=str(error),
            exc_info=True,
            query=query,
        )
        return ""


def run_gpt_researcher_sync(query: str, report_type: str = "research_report") -> str:
    """
    Synchronous wrapper for GPT Researcher.

    Args:
        query: The research question or topic
        report_type: Type of report to generate (default: "research_report")

    Returns:
        String containing the research report
    """
    return asyncio.run(research_with_gpt_researcher(query, report_type))


async def generate_vs_competitor_content(
    project_name: str,
    competitor_name: str,
    competitor_url: str,
    project_summary: str,
    competitor_description: str,
) -> str:
    """
    Generate detailed comparison content between project and competitor using GPT Researcher.

    Args:
        project_name: Name of the user's project
        competitor_name: Name of the competitor
        competitor_url: URL of the competitor
        project_summary: Summary of the user's project
        competitor_description: Description of the competitor

    Returns:
        Detailed research report comparing the two products
    """
    query = f"""
    Create a comprehensive comparison between {project_name} and {competitor_name}.

    {project_name} Details:
    {project_summary}

    {competitor_name} Details:
    URL: {competitor_url}
    Description: {competitor_description}

    Please compare:
    1. Key features and capabilities
    2. Pricing and value proposition
    3. Target audience and use cases
    4. Strengths and weaknesses of each
    5. Which solution is better for different scenarios

    Focus on factual, balanced analysis.
    """

    try:
        researcher = GPTResearcher(query=query, report_type="research_report")
        await researcher.conduct_research()
        report = await researcher.write_report()
        return report
    except Exception as error:
        logger.error(
            "[GPT Researcher] Error generating vs competitor content",
            error=str(error),
            exc_info=True,
            project_name=project_name,
            competitor_name=competitor_name,
        )
        return ""


def generate_vs_competitor_content_sync(
    project_name: str,
    competitor_name: str,
    competitor_url: str,
    project_summary: str,
    competitor_description: str,
) -> str:
    """
    Synchronous wrapper for generating vs competitor content.
    """
    return asyncio.run(
        generate_vs_competitor_content(
            project_name, competitor_name, competitor_url, project_summary, competitor_description
        )
    )
