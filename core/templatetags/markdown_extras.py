import markdown as md
from django import template
from django.conf import settings
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
@stringfilter
def markdown(value):
    md_instance = md.Markdown(extensions=["tables"])

    html = md_instance.convert(value)

    return mark_safe(html)


@register.filter
@stringfilter
def replace_quotes(value):
    return value.replace('"', "'")


@register.simple_tag
def mjml_configured():
    return bool(settings.MJML_URL)
