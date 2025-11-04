from django.contrib import sitemaps
from django.contrib.sitemaps import GenericSitemap
from django.urls import reverse

from core.models import BlogPost
from docs.views import get_docs_navigation


class StaticViewSitemap(sitemaps.Sitemap):
    """Generate Sitemap for the site"""

    priority = 0.9
    protocol = "https"

    def items(self):
        """Identify items that will be in the Sitemap

        Returns:
            List: urlNames that will be in the Sitemap
        """
        return [
            "landing",
            "home",
            "uses",
            "pricing",
            "blog_posts",
        ]

    def location(self, item):
        """Get location for each item in the Sitemap

        Args:
            item (str): Item from the items function

        Returns:
            str: Url for the sitemap item
        """
        return reverse(item)


class DocsSitemap(sitemaps.Sitemap):
    """Generate Sitemap for documentation pages"""

    priority = 0.8
    protocol = "https"
    changefreq = "weekly"

    def items(self):
        """Get all documentation pages from the navigation structure

        Returns:
            List: List of dicts with category and page slugs for each doc page
        """
        doc_pages = []
        navigation = get_docs_navigation()

        for category_info in navigation:
            category_slug = category_info["category_slug"]
            for page_info in category_info["pages"]:
                page_slug = page_info["slug"]
                doc_pages.append(
                    {
                        "category": category_slug,
                        "page": page_slug,
                    }
                )

        return doc_pages

    def location(self, item):
        """Get location for each doc page in the Sitemap

        Args:
            item (dict): Dictionary with category and page slugs

        Returns:
            str: URL for the sitemap item
        """
        return f"/docs/{item['category']}/{item['page']}/"


sitemaps = {
    "static": StaticViewSitemap,
    "blog": GenericSitemap(
        {"queryset": BlogPost.objects.all(), "date_field": "created_at"},
        priority=0.85,
        protocol="https",
    ),
    "docs": DocsSitemap,
}
