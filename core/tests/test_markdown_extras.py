from django.test import override_settings

from core.templatetags.markdown_extras import (
    markdown as markdown_filter,
    mjml_configured,
    replace,
    replace_quotes,
)


class TestMarkdownFilter:
    def test_converts_markdown_to_html(self):
        markdown_text = "# Heading"

        rendered_html = markdown_filter(markdown_text)

        assert "<h1>Heading</h1>" in rendered_html


class TestReplaceQuotesFilter:
    def test_replaces_double_quotes_with_single_quotes(self):
        text_with_quotes = 'Say "hello" to "world"'

        replaced_text = replace_quotes(text_with_quotes)

        assert replaced_text == "Say 'hello' to 'world'"


class TestReplaceFilter:
    def test_replaces_first_argument_with_second_argument(self):
        source_text = "hello-world"

        replaced_text = replace(source_text, "-,_")

        assert replaced_text == "hello_world"

    def test_returns_original_value_when_arg_has_no_comma(self):
        source_text = "hello-world"

        replaced_text = replace(source_text, "invalid-arg")

        assert replaced_text == source_text


class TestMjmlConfiguredTag:
    @override_settings(MJML_URL="http://mjml-service")
    def test_returns_true_when_mjml_url_is_configured(self):
        assert mjml_configured() is True

    @override_settings(MJML_URL="")
    def test_returns_false_when_mjml_url_is_empty(self):
        assert mjml_configured() is False
