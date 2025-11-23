"""
Django Admin Configuration for SEO Content Validator
"""

from django.contrib import admin
from .models import Guideline, Article, ValidationHistory


@admin.register(Guideline)
class GuidelineAdmin(admin.ModelAdmin):
    """Admin interface for Guideline model"""

    list_display = [
        'name', 'created_by', 'status', 'total_keywords',
        'is_active', 'created_at'
    ]
    list_filter = ['status', 'is_active', 'created_at']
    search_fields = ['name', 'notes']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'status',
        'error_message', 'total_keywords'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'created_by', 'status', 'error_message', 'is_active')
        }),
        ('File Upload', {
            'fields': ('original_file', 'original_filename')
        }),
        ('Structure Requirements', {
            'fields': (
                ('paragraphs_min', 'paragraphs_max'),
                ('images_min', 'images_max'),
                ('headings_min', 'headings_max'),
                ('characters_min', 'characters_max'),
                ('words_min', 'words_max'),
            )
        }),
        ('Quartile Data', {
            'fields': ('total_keywords', 'keywords_q1', 'keywords_q2', 'keywords_q3', 'keywords_q4'),
            'classes': ('collapse',)  # Collapsed by default
        }),
        ('Additional Data', {
            'fields': ('other_terms', 'questions', 'notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        """Set created_by to current user if creating"""
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Admin interface for Article model"""

    list_display = [
        'title', 'guideline', 'created_by', 'target_quartile',
        'validation_score', 'word_count', 'is_published', 'created_at'
    ]
    list_filter = ['target_quartile', 'is_published', 'created_at', 'guideline']
    search_fields = ['title', 'content']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'last_validated_at',
        'validation_score', 'validation_summary', 'word_count', 'character_count'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'title', 'guideline', 'created_by', 'target_quartile')
        }),
        ('Content', {
            'fields': ('content', 'content_file')
        }),
        ('Validation Results', {
            'fields': (
                'last_validated_at', 'validation_score', 'validation_summary',
                'validation_results'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('word_count', 'character_count', 'is_published'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['validate_articles', 'publish_articles', 'unpublish_articles']

    def save_model(self, request, obj, form, change):
        """Set created_by to current user if creating"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def validate_articles(self, request, queryset):
        """Admin action to validate selected articles"""
        count = 0
        for article in queryset:
            try:
                article.validate(force=True)
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error validating '{article.title}': {str(e)}",
                    level='ERROR'
                )

        self.message_user(
            request,
            f"Successfully validated {count} article(s)",
            level='SUCCESS'
        )

    validate_articles.short_description = "Validate selected articles"

    def publish_articles(self, request, queryset):
        """Admin action to publish selected articles"""
        count = queryset.update(is_published=True)
        self.message_user(
            request,
            f"Published {count} article(s)",
            level='SUCCESS'
        )

    publish_articles.short_description = "Publish selected articles"

    def unpublish_articles(self, request, queryset):
        """Admin action to unpublish selected articles"""
        count = queryset.update(is_published=False)
        self.message_user(
            request,
            f"Unpublished {count} article(s)",
            level='SUCCESS'
        )

    unpublish_articles.short_description = "Unpublish selected articles"


@admin.register(ValidationHistory)
class ValidationHistoryAdmin(admin.ModelAdmin):
    """Admin interface for ValidationHistory model"""

    list_display = [
        'article', 'target_quartile', 'validation_score',
        'word_count', 'validated_at'
    ]
    list_filter = ['target_quartile', 'validated_at']
    search_fields = ['article__title', 'validation_summary']
    readonly_fields = [
        'id', 'article', 'content_snapshot', 'word_count',
        'target_quartile', 'validation_score', 'validation_summary',
        'validation_results', 'validated_at'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'article', 'target_quartile', 'validated_at')
        }),
        ('Content Snapshot', {
            'fields': ('content_snapshot', 'word_count'),
            'classes': ('collapse',)
        }),
        ('Validation Results', {
            'fields': ('validation_score', 'validation_summary', 'validation_results')
        }),
    )

    def has_add_permission(self, request):
        """Prevent manual creation"""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing"""
        return False
