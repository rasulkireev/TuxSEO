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
    ReferrerBanner,
)


@admin.register(ReferrerBanner)
class ReferrerBannerAdmin(admin.ModelAdmin):
    list_display = (
        "referrer",
        "referrer_printable_name",
        "discount_percentage",
        "coupon_code",
        "expiry_date",
        "is_active",
        "should_display",
    )
    list_filter = ("is_active", "expiry_date")
    search_fields = ("referrer", "referrer_printable_name", "coupon_code")
    readonly_fields = ("created_at", "updated_at", "is_expired", "should_display")
    fieldsets = (
        (
            "Banner Information",
            {
                "fields": (
                    "referrer",
                    "referrer_printable_name",
                    "is_active",
                )
            },
        ),
        (
            "Design",
            {
                "fields": (
                    "background_color",
                    "text_color",
                ),
                "description": "Customize banner appearance using Tailwind CSS classes",
            },
        ),
        (
            "Discount Details",
            {
                "fields": (
                    "discount_amount",
                    "coupon_code",
                    "expiry_date",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_expired",
                    "should_display",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


admin.site.register(Profile)
admin.site.register(BlogPost)
admin.site.register(Project)
admin.site.register(BlogPostTitleSuggestion)
admin.site.register(GeneratedBlogPost)
admin.site.register(AutoSubmissionSetting)
admin.site.register(ProjectPage)
admin.site.register(EmailSent)
