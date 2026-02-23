from pathlib import Path
from unittest.mock import patch

import pytest
from django.http import Http404, HttpResponse
from django.test import RequestFactory, override_settings

from docs.views import (
    docs_page_view,
    get_docs_navigation,
    get_flat_page_list,
    get_previous_and_next_pages,
    load_navigation_config,
)


@pytest.fixture
def request_factory():
    return RequestFactory()


def create_markdown_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@override_settings(BASE_DIR="/tmp/nonexistent-base-dir")
def test_load_navigation_config_returns_empty_dict_when_file_is_missing():
    assert load_navigation_config() == {}


def test_load_navigation_config_reads_navigation_yaml(tmp_path):
    navigation_file = tmp_path / "docs" / "navigation.yaml"
    navigation_file.parent.mkdir(parents=True, exist_ok=True)
    navigation_file.write_text(
        """
navigation:
  getting-started:
    - introduction
  features:
    - blog-post-suggestions
""",
        encoding="utf-8",
    )

    with override_settings(BASE_DIR=tmp_path):
        navigation_config = load_navigation_config()

    assert navigation_config == {
        "getting-started": ["introduction"],
        "features": ["blog-post-suggestions"],
    }


def test_get_docs_navigation_respects_custom_order_and_includes_remaining_items(tmp_path):
    create_markdown_file(
        tmp_path / "docs" / "content" / "getting-started" / "quickstart.md",
        "# Quickstart",
    )
    create_markdown_file(
        tmp_path / "docs" / "content" / "getting-started" / "introduction.md",
        "# Introduction",
    )
    create_markdown_file(
        tmp_path / "docs" / "content" / "features" / "blog-post-suggestions.md",
        "# Features",
    )

    navigation_file = tmp_path / "docs" / "navigation.yaml"
    navigation_file.parent.mkdir(parents=True, exist_ok=True)
    navigation_file.write_text(
        """
navigation:
  features:
    - blog-post-suggestions
  getting-started:
    - introduction
""",
        encoding="utf-8",
    )

    with override_settings(BASE_DIR=tmp_path):
        navigation = get_docs_navigation()

    assert [item["category_slug"] for item in navigation] == ["features", "getting-started"]

    getting_started_pages = navigation[1]["pages"]
    assert [page["slug"] for page in getting_started_pages] == ["introduction", "quickstart"]


def test_get_flat_page_list_flattens_navigation_structure():
    navigation = [
        {
            "category": "Getting Started",
            "category_slug": "getting-started",
            "pages": [
                {
                    "slug": "introduction",
                    "title": "Introduction",
                    "url": "/docs/getting-started/introduction/",
                },
                {
                    "slug": "quickstart",
                    "title": "Quickstart",
                    "url": "/docs/getting-started/quickstart/",
                },
            ],
        }
    ]

    flat_pages = get_flat_page_list(navigation)

    assert len(flat_pages) == 2
    assert flat_pages[0]["page_slug"] == "introduction"
    assert flat_pages[1]["page_slug"] == "quickstart"


def test_get_previous_and_next_pages_returns_neighbor_pages():
    navigation = [
        {
            "category": "Getting Started",
            "category_slug": "getting-started",
            "pages": [
                {
                    "slug": "introduction",
                    "title": "Introduction",
                    "url": "/docs/getting-started/introduction/",
                },
                {
                    "slug": "quickstart",
                    "title": "Quickstart",
                    "url": "/docs/getting-started/quickstart/",
                },
            ],
        },
        {
            "category": "Features",
            "category_slug": "features",
            "pages": [
                {
                    "slug": "blog-post-suggestions",
                    "title": "Blog Post Suggestions",
                    "url": "/docs/features/blog-post-suggestions/",
                }
            ],
        },
    ]

    previous_page, next_page = get_previous_and_next_pages(
        navigation=navigation,
        current_category="getting-started",
        current_page="quickstart",
    )

    assert previous_page["page_slug"] == "introduction"
    assert next_page["page_slug"] == "blog-post-suggestions"


def test_docs_page_view_loads_markdown_and_builds_context(tmp_path, request_factory):
    create_markdown_file(
        tmp_path / "docs" / "content" / "getting-started" / "introduction.md",
        """---
title: Intro Page
description: Intro description
keywords: intro,getting-started
author: Greg
canonical_url: https://docs.example.com/getting-started/introduction
---
# Welcome

This is the introduction page.
""",
    )

    navigation_file = tmp_path / "docs" / "navigation.yaml"
    navigation_file.parent.mkdir(parents=True, exist_ok=True)
    navigation_file.write_text(
        """
navigation:
  getting-started:
    - introduction
""",
        encoding="utf-8",
    )

    request = request_factory.get("/docs/getting-started/introduction/")

    captured_context = {}

    def fake_render(_request, _template, context):
        captured_context.update(context)
        return HttpResponse("ok")

    with override_settings(BASE_DIR=tmp_path), patch("docs.views.render", side_effect=fake_render):
        response = docs_page_view(request, category="getting-started", page="introduction")

    assert response.status_code == 200
    assert captured_context["page_title"] == "Intro Page"
    assert captured_context["meta_description"] == "Intro description"
    assert "<h1>Welcome</h1>" in captured_context["content"]


def test_docs_page_view_raises_404_for_missing_file(tmp_path, request_factory):
    request = request_factory.get("/docs/missing/page/")

    with override_settings(BASE_DIR=tmp_path), pytest.raises(Http404) as exc_info:
        docs_page_view(request, category="missing", page="page")

    assert "Documentation page not found" in str(exc_info.value)
