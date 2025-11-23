"""
Django Models for SEO Content Validator

Stores pre-computed guideline data with Q1/Q2/Q3/Q4 quartile information.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class Guideline(models.Model):
    """
    Pre-computed guideline with quartile data.

    Stores all Q1, Q2, Q3, Q4 boundaries and targets for fast validation.
    """

    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Guideline name (e.g., 'Hemp Shoes SEO Guide')")

    # Ownership and timestamps
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guidelines'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # File storage (S3)
    original_file = models.FileField(
        upload_to='guidelines/originals/%Y/%m/',
        null=True,
        blank=True,
        help_text="Original guideline file uploaded by user"
    )
    original_filename = models.CharField(max_length=255, blank=True)

    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending Processing'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, help_text="Error message if processing failed")

    # Structure requirements
    paragraphs_min = models.IntegerField(default=0)
    paragraphs_max = models.IntegerField(null=True, blank=True, help_text="NULL means infinity")
    images_min = models.IntegerField(default=0)
    images_max = models.IntegerField(default=0)
    headings_min = models.IntegerField(default=0)
    headings_max = models.IntegerField(default=0)
    characters_min = models.IntegerField(default=0)
    characters_max = models.IntegerField(default=0)
    words_min = models.IntegerField(default=0)
    words_max = models.IntegerField(default=0)

    # Pre-computed quartile data (JSON fields)
    # Each contains: {keyword: {min, max, boundary, target}}
    keywords_q1 = models.JSONField(
        default=dict,
        help_text="Q1 (Conservative - 12.5th percentile) keyword targets"
    )
    keywords_q2 = models.JSONField(
        default=dict,
        help_text="Q2 (Median - 37.5th percentile) keyword targets"
    )
    keywords_q3 = models.JSONField(
        default=dict,
        help_text="Q3 (Recommended - 62.5th percentile) keyword targets"
    )
    keywords_q4 = models.JSONField(
        default=dict,
        help_text="Q4 (Aggressive - 87.5th percentile) keyword targets"
    )

    # Other data
    other_terms = models.JSONField(
        default=list,
        help_text="Other relevant terms to consider"
    )
    questions = models.JSONField(
        default=list,
        help_text="Questions that should be answered in content"
    )
    notes = models.TextField(blank=True)

    # Metadata
    total_keywords = models.IntegerField(default=0, help_text="Total number of keywords")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['is_active', '-created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"

    def get_quartile_data(self, quartile: str):
        """
        Get quartile data for specified quartile.

        Args:
            quartile: "Q1", "Q2", "Q3", or "Q4"

        Returns:
            Dictionary of keyword data for that quartile
        """
        quartile_map = {
            'Q1': self.keywords_q1,
            'Q2': self.keywords_q2,
            'Q3': self.keywords_q3,
            'Q4': self.keywords_q4,
        }
        return quartile_map.get(quartile.upper(), self.keywords_q3)

    def to_stored_guideline(self):
        """
        Convert to StoredGuideline object for use with FastArticleValidator.

        Returns:
            StoredGuideline object
        """
        from guideline_storage import StoredGuideline

        return StoredGuideline(
            id=str(self.id),
            name=self.name,
            created_at=self.created_at.isoformat(),
            paragraphs_min=self.paragraphs_min,
            paragraphs_max=self.paragraphs_max,
            images_min=self.images_min,
            images_max=self.images_max,
            headings_min=self.headings_min,
            headings_max=self.headings_max,
            characters_min=self.characters_min,
            characters_max=self.characters_max,
            words_min=self.words_min,
            words_max=self.words_max,
            keywords_q1=self.keywords_q1,
            keywords_q2=self.keywords_q2,
            keywords_q3=self.keywords_q3,
            keywords_q4=self.keywords_q4,
            other_terms=self.other_terms,
            questions=self.questions,
            notes=self.notes
        )


class Article(models.Model):
    """
    Article being validated against a guideline.
    """

    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500, blank=True)

    # Relationships
    guideline = models.ForeignKey(
        Guideline,
        on_delete=models.CASCADE,
        related_name='articles'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articles'
    )

    # Content
    content = models.TextField(help_text="Article content (markdown/HTML)")

    # File storage (S3) - optional if content is in database
    content_file = models.FileField(
        upload_to='articles/%Y/%m/',
        null=True,
        blank=True,
        help_text="Article file if uploaded"
    )

    # Validation settings
    target_quartile = models.CharField(
        max_length=2,
        choices=[('Q1', 'Q1'), ('Q2', 'Q2'), ('Q3', 'Q3'), ('Q4', 'Q4')],
        default='Q3',
        help_text="Target quartile for validation"
    )

    # Validation results (cached)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    validation_score = models.FloatField(null=True, blank=True, help_text="0-100 score")
    validation_summary = models.CharField(max_length=500, blank=True)
    validation_results = models.JSONField(
        null=True,
        blank=True,
        help_text="Complete validation results from FastArticleValidator"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    word_count = models.IntegerField(default=0)
    character_count = models.IntegerField(default=0)

    # Status
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['guideline', '-updated_at']),
            models.Index(fields=['created_by', '-updated_at']),
            models.Index(fields=['is_published', '-updated_at']),
        ]

    def __str__(self):
        return f"{self.title or 'Untitled'} - {self.guideline.name}"

    def validate(self, force=False):
        """
        Validate article against guideline using FastArticleValidator.

        Args:
            force: If True, re-validate even if recently validated

        Returns:
            Validation result dictionary
        """
        from fast_validator import FastArticleValidator

        # Check if recently validated (within 1 minute)
        if not force and self.last_validated_at:
            time_since = timezone.now() - self.last_validated_at
            if time_since.total_seconds() < 60:
                return self.validation_results

        # Get stored guideline
        stored_guideline = self.guideline.to_stored_guideline()

        # Create validator
        validator = FastArticleValidator(stored_guideline, target_quartile=self.target_quartile)

        # Validate
        result = validator.validate(self.content)

        # Cache results
        self.last_validated_at = timezone.now()
        self.validation_score = result.overall_score
        self.validation_summary = result.summary
        self.validation_results = result.to_dict()
        self.save(update_fields=['last_validated_at', 'validation_score', 'validation_summary', 'validation_results'])

        return self.validation_results


class ValidationHistory(models.Model):
    """
    Track validation history for an article (optional - for analytics).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='validation_history')

    # Snapshot of content at validation time
    content_snapshot = models.TextField()
    word_count = models.IntegerField()

    # Validation results
    target_quartile = models.CharField(max_length=2)
    validation_score = models.FloatField()
    validation_summary = models.CharField(max_length=500)
    validation_results = models.JSONField()

    # Timestamp
    validated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-validated_at']
        verbose_name_plural = 'Validation histories'
        indexes = [
            models.Index(fields=['article', '-validated_at']),
        ]

    def __str__(self):
        return f"{self.article.title} - {self.validated_at.strftime('%Y-%m-%d %H:%M')} - Score: {self.validation_score}"
