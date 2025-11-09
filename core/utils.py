import random
import string
from urllib.request import urlopen

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.forms.utils import ErrorList
from pydantic_ai import capture_run_messages

from core.choices import OGImageStyle
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


class DivErrorList(ErrorList):
    def __str__(self):
        return self.as_divs()

    def as_divs(self):
        if not self:
            return ""
        return f"""
            <div class="p-4 my-4 bg-red-50 rounded-md border border-red-600 border-solid">
              <div class="flex">
                <div class="flex-shrink-0">
                  <!-- Heroicon name: solid/x-circle -->
                  <svg class="w-5 h-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                  </svg>
                </div>
                <div class="ml-3 text-sm text-red-700">
                      {"".join([f"<p>{e}</p>" for e in self])}
                </div>
              </div>
            </div>
         """  # noqa: E501


def replace_placeholders(data, blog_post):
    """
    Recursively replace values in curly braces (e.g., '{{ slug }}')
    in a dict with the corresponding attribute from blog_post.
    """
    if isinstance(data, dict):
        return {k: replace_placeholders(v, blog_post) for k, v in data.items()}
    elif isinstance(data, list):
        return [replace_placeholders(item, blog_post) for item in data]
    elif isinstance(data, str):
        import re

        def repl(match):
            attr = match.group(1).strip()
            # Support nested attributes (e.g., title.title)
            value = blog_post
            for part in attr.split("."):
                value = getattr(value, part, match.group(0))
                if value == match.group(0):
                    break
            return str(value)

        return re.sub(r"\{\{\s*(.*?)\s*\}\}", repl, data)
    else:
        return data


def get_og_image_prompt(style: str, category: str) -> str:
    """
    Generate a style-specific prompt for OG image generation.

    Args:
        style: The OG image style from OGImageStyle choices
        category: The blog post category

    Returns:
        A prompt string optimized for the selected style
    """
    base_format = "1200x630 pixels aspect ratio. NO TEXT, NO WORDS, NO LETTERS."

    style_prompts = {
        OGImageStyle.MODERN_GRADIENT: f"Modern gradient background for a social media post about {category}. Contemporary smooth color transitions, flowing shapes, clean composition. {base_format}",  # noqa: E501
        OGImageStyle.MINIMALIST_CLEAN: f"Minimalist clean background for a social media post about {category}. Simple geometric shapes, plenty of white space, subtle colors, elegant and professional. {base_format}",  # noqa: E501
        OGImageStyle.BOLD_TYPOGRAPHY: f"Bold graphic background for a social media post about {category}. Strong geometric shapes, high contrast, eye-catching composition, modern and dynamic. {base_format}",  # noqa: E501
        OGImageStyle.TECH_ABSTRACT: f"Tech abstract background for a social media post about {category}. Geometric patterns, grid lines, digital aesthetic, futuristic feel, technology-inspired visuals. {base_format}",  # noqa: E501
        OGImageStyle.PROFESSIONAL_CORPORATE: f"Professional corporate background for a social media post about {category}. Polished appearance, business-friendly colors, clean lines, sophisticated composition. {base_format}",  # noqa: E501
        OGImageStyle.CREATIVE_ARTISTIC: f"Creative artistic background for a social media post about {category}. Unique visual elements, artistic flair, expressive composition, vibrant and imaginative. {base_format}",  # noqa: E501
        OGImageStyle.DARK_MODE: f"Dark mode background for a social media post about {category}. Dark background with vibrant accent colors, modern contrast, sleek and contemporary aesthetic. {base_format}",  # noqa: E501
        OGImageStyle.VIBRANT_COLORFUL: f"Vibrant colorful background for a social media post about {category}. Bold colors, energetic composition, dynamic visual elements, eye-catching and lively. {base_format}",  # noqa: E501
    }

    return style_prompts.get(
        style,
        f"Abstract modern geometric background for a social media post about {category}. Clean minimalist design with vibrant gradients, smooth shapes, professional aesthetic. {base_format}",  # noqa: E501
    )


def download_image_from_url(
    image_url: str, field_name: str, instance_id: str | int
) -> ContentFile | None:
    """
    Download an image from a URL and return a ContentFile ready to be saved to an ImageField.

    Args:
        image_url: The URL of the image to download
        field_name: The name of the field (e.g., 'icon', 'image') for logging and filename
        instance_id: The ID of the model instance for logging and filename

    Returns:
        ContentFile containing the image data, or None if download fails
    """
    try:
        logger.info(
            f"[DownloadImage] Downloading {field_name} from URL",
            image_url=image_url,
            field_name=field_name,
            instance_id=instance_id,
        )

        image_response = urlopen(image_url)
        image_content = ContentFile(image_response.read())

        logger.info(
            f"[DownloadImage] Successfully downloaded {field_name}",
            image_url=image_url,
            field_name=field_name,
            instance_id=instance_id,
        )

        return image_content

    except Exception as error:
        logger.error(
            f"[DownloadImage] Failed to download {field_name} from URL",
            error=str(error),
            exc_info=True,
            image_url=image_url,
            field_name=field_name,
            instance_id=instance_id,
        )
        return None


def get_jina_embedding(text: str) -> list[float] | None:
    """
    Get embedding from Jina API for the given text.

    Args:
        text: The text to generate an embedding for

    Returns:
        A list of floats representing the embedding vector, or None if the request fails
    """
    url = "https://api.jina.ai/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.JINA_READER_API_KEY}",
    }
    data = {"model": "jina-embeddings-v3", "task": "text-matching", "input": [text]}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=20)
        response.raise_for_status()
        result = response.json()

        if result.get("data") and len(result["data"]) > 0:
            embedding = result["data"][0]["embedding"]
            logger.info(
                "[GetJinaEmbedding] Successfully generated embedding",
                embedding_dimensions=len(embedding),
            )
            return embedding
        else:
            logger.error(
                "[GetJinaEmbedding] Unexpected response format from Jina API",
                result=result,
            )
            return None

    except requests.exceptions.RequestException as request_error:
        logger.error(
            "[GetJinaEmbedding] Error getting embedding from Jina API",
            error=str(request_error),
            exc_info=True,
        )
        return None


def generate_random_key():
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(10))


def run_agent_synchronously(agent, input_string, deps=None, function_name="", model_name=""):
    """
    Run a PydanticAI agent synchronously.

    Args:
        agent: The PydanticAI agent to run
        input_string: The input string to pass to the agent
        deps: Optional dependencies to pass to the agent

    Returns:
        The result of the agent run

    Raises:
        RuntimeError: If the agent execution fails
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    with capture_run_messages() as messages:
        try:
            logger.info(
                "[Run Agent Synchronously] Running agent",
                messages=messages,
                input_string=input_string,
                deps=deps,
                function_name=function_name,
                model_name=model_name,
            )
            if deps is not None:
                result = loop.run_until_complete(agent.run(input_string, deps=deps))
            else:
                result = loop.run_until_complete(agent.run(input_string))

            logger.info(
                "[Run Agent Synchronously] Agent run successfully",
                messages=messages,
                input_string=input_string,
                deps=deps,
                result=result,
                function_name=function_name,
                model_name=model_name,
            )
            return result
        except Exception as e:
            logger.error(
                "[Run Agent Synchronously] Failed execution",
                messages=messages,
                exc_info=True,
                error=str(e),
                function_name=function_name,
                model_name=model_name,
            )
            raise


def get_html_content(url):
    html_content = ""
    try:
        html_response = requests.get(url, timeout=30)
        html_response.raise_for_status()
        html_content = html_response.text
    except requests.exceptions.RequestException as e:
        logger.warning(
            "[Get HTML Content] Could not fetch HTML content",
            exc_info=True,
            error=str(e),
            url=url,
        )
    except Exception as e:
        logger.warning(
            "[Get HTML Content] Unexpected error",
            exc_info=True,
            error=str(e),
            url=url,
        )

    return html_content


def get_markdown_content(url):
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.JINA_READER_API_KEY}",
    }

    try:
        response = requests.get(jina_url, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json().get("data", {})

        logger.info(
            "[Get Markdown Content] Successfully fetched content from Jina Reader",
            data=data,
            url=url,
        )

        return (
            data.get("title", "")[:500],
            data.get("description", ""),
            data.get("content", ""),
        )

    except requests.exceptions.RequestException as e:
        logger.error(
            "[Get Markdown Content] Error fetching content from Jina Reader",
            error=str(e),
            exc_info=True,
            url=url,
        )
        return ("", "", "")
