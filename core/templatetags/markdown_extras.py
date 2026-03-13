import markdown as md
from bs4 import BeautifulSoup
from django import template
from django.conf import settings
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
@stringfilter
def markdown(value):
    md_instance = md.Markdown(extensions=["tables", "fenced_code"])

    html = md_instance.convert(value)
    soup = BeautifulSoup(html, "html.parser")

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if href.startswith("http://") or href.startswith("https://"):
            link["target"] = "_blank"
            link["rel"] = ["noopener", "noreferrer"]

    for pre in soup.find_all("pre"):
        code = pre.find("code")
        if code is None:
            continue

        snippet_wrapper = soup.new_tag(
            "div",
            attrs={
                "class": "code-snippet",
                "data-controller": "copy",
            },
        )
        copy_button = soup.new_tag(
            "button",
            attrs={
                "type": "button",
                "data-action": "copy#copy",
                "data-copy-target": "button",
                "class": (
                    "inline-flex items-center px-2 py-1 mb-2 text-xs font-medium text-white "
                    "bg-gray-900 rounded border border-gray-900 hover:bg-gray-800 "
                    "focus:outline-none focus:ring-2 focus:ring-gray-500"
                ),
            },
        )
        copy_button.string = "Copy"
        copy_source = soup.new_tag(
            "textarea",
            attrs={
                "data-copy-target": "source",
                "class": "sr-only",
                "readonly": "",
            },
        )
        copy_source.string = code.get_text()

        pre.replace_with(snippet_wrapper)
        snippet_wrapper.append(copy_button)
        snippet_wrapper.append(pre)
        snippet_wrapper.append(copy_source)

    return mark_safe(str(soup))


@register.filter
@stringfilter
def replace_quotes(value):
    return value.replace('"', "'")


@register.filter
@stringfilter
def replace(value, arg):
    """
    Replace occurrences of old string with new string.
    Usage: {{ value|replace:"old,new" }}
    """
    if "," not in arg:
        return value
    old, new = arg.split(",", 1)
    return value.replace(old, new)


@register.simple_tag
def mjml_configured():
    return bool(settings.MJML_URL)
