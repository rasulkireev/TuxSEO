from django.contrib import admin

from core.models import (
    AutoSubmissionSetting,
    BlogPost,
    BlogPostTitleSuggestion,
    EmailSent,
    GeneratedBlogPost,
    Profile,
    Project,
    ProjectPage,
)

admin.site.register(Profile)
admin.site.register(BlogPost)
admin.site.register(Project)
admin.site.register(BlogPostTitleSuggestion)
admin.site.register(GeneratedBlogPost)
admin.site.register(AutoSubmissionSetting)
admin.site.register(ProjectPage)
admin.site.register(EmailSent)
