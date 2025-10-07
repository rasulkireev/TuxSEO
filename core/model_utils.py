import random
import string

import requests
from pydantic_ai import capture_run_messages
from sentry_sdk import logger

from tuxseo import settings


def generate_random_key():
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(10))


def run_agent_synchronously(agent, input_string, deps=None, function_name="", model_name=""):
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    with capture_run_messages() as messages:
        logger.info(
            "[Run Agent Synchronously] Running agent",
            extra={
                "messages": messages,
                "input_string": input_string,
                "deps": deps,
                "function_name": function_name,
                "model_name": model_name,
            },
        )
        if deps is not None:
            result = loop.run_until_complete(agent.run(input_string, deps=deps))
        else:
            result = loop.run_until_complete(agent.run(input_string))

        logger.info(
            "[Run Agent Synchronously] Agent run successfully",
            extra={
                "messages": messages,
                "input_string": input_string,
                "deps": deps,
                "result": result,
                "function_name": function_name,
                "model_name": model_name,
            },
        )
        return result


def get_html_content(url):
    html_content = ""

    html_response = requests.get(url, timeout=30)
    html_response.raise_for_status()
    html_content = html_response.text

    return html_content


def get_markdown_content(url):
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.JINA_READER_API_KEY}",
    }

    response = requests.get(jina_url, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json().get("data", {})

    return (
        data.get("title", "")[:500],
        data.get("description", ""),
        data.get("content", ""),
    )
