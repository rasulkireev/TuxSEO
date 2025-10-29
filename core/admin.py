from django.contrib import admin

from core.models import (
    AutoSubmissionSetting,
    BlogPost,
    BlogPostTitleSuggestion,
    GeneratedBlogPost,
    Profile,
    Project,
    SitemapPage,
)

admin.site.register(Profile)
admin.site.register(BlogPost)
admin.site.register(Project)
admin.site.register(BlogPostTitleSuggestion)
admin.site.register(GeneratedBlogPost)
admin.site.register(AutoSubmissionSetting)
admin.site.register(SitemapPage)
