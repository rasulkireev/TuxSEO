"""
Django REST Framework Serializers for SEO Content Validator
"""

from rest_framework import serializers
from .models import Guideline, Article, ValidationHistory
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    """User serializer for nested relationships"""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class GuidelineSerializer(serializers.ModelSerializer):
    """
    Serializer for Guideline model.
    """

    created_by = UserSerializer(read_only=True)
    original_file_url = serializers.SerializerMethodField()

    class Meta:
        model = Guideline
        fields = [
            'id', 'name', 'created_by', 'created_at', 'updated_at',
            'original_file', 'original_file_url', 'original_filename',
            'status', 'error_message',
            'paragraphs_min', 'paragraphs_max',
            'images_min', 'images_max',
            'headings_min', 'headings_max',
            'characters_min', 'characters_max',
            'words_min', 'words_max',
            'keywords_q1', 'keywords_q2', 'keywords_q3', 'keywords_q4',
            'other_terms', 'questions', 'notes',
            'total_keywords', 'is_active'
        ]
        read_only_fields = [
            'id', 'created_by', 'created_at', 'updated_at',
            'status', 'error_message', 'total_keywords'
        ]

    def get_original_file_url(self, obj):
        """Get S3 URL for original file"""
        if obj.original_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.original_file.url)
            return obj.original_file.url
        return None


class GuidelineListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing guidelines (excludes heavy JSON fields).
    """

    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Guideline
        fields = [
            'id', 'name', 'created_by', 'created_at', 'updated_at',
            'status', 'total_keywords', 'is_active'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class GuidelineUploadSerializer(serializers.Serializer):
    """
    Serializer for guideline file upload.
    """

    name = serializers.CharField(max_length=200, help_text="Guideline name")
    file = serializers.FileField(help_text="Guideline text file (.txt)")

    def validate_file(self, value):
        """Validate uploaded file"""
        # Check file size (max 5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 5MB")

        # Check file extension
        if not value.name.endswith('.txt'):
            raise serializers.ValidationError("Only .txt files are allowed")

        return value


class ArticleSerializer(serializers.ModelSerializer):
    """
    Serializer for Article model.
    """

    created_by = UserSerializer(read_only=True)
    guideline_name = serializers.CharField(source='guideline.name', read_only=True)
    content_file_url = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            'id', 'title', 'guideline', 'guideline_name',
            'created_by', 'content', 'content_file', 'content_file_url',
            'target_quartile',
            'last_validated_at', 'validation_score', 'validation_summary',
            'validation_results',
            'created_at', 'updated_at',
            'word_count', 'character_count', 'is_published'
        ]
        read_only_fields = [
            'id', 'created_by', 'guideline_name', 'created_at', 'updated_at',
            'last_validated_at', 'validation_score', 'validation_summary',
            'validation_results', 'word_count', 'character_count'
        ]

    def get_content_file_url(self, obj):
        """Get S3 URL for content file"""
        if obj.content_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.content_file.url)
            return obj.content_file.url
        return None


class ArticleCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating articles.
    """

    class Meta:
        model = Article
        fields = [
            'title', 'guideline', 'content', 'target_quartile'
        ]

    def create(self, validated_data):
        """Create article and calculate word/character counts"""
        content = validated_data.get('content', '')

        # Calculate counts
        import re
        clean_content = re.sub(r'<[^>]+>', '', content)
        word_count = len(re.findall(r'\b\w+\b', clean_content))
        char_count = len(clean_content)

        validated_data['word_count'] = word_count
        validated_data['character_count'] = char_count

        return super().create(validated_data)


class ArticleValidateSerializer(serializers.Serializer):
    """
    Serializer for validating article content.
    """

    content = serializers.CharField(help_text="Article content to validate")
    guideline_id = serializers.UUIDField(help_text="Guideline ID to validate against")
    target_quartile = serializers.ChoiceField(
        choices=['Q1', 'Q2', 'Q3', 'Q4'],
        default='Q3',
        help_text="Target quartile"
    )


class ValidationHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for ValidationHistory model.
    """

    article_title = serializers.CharField(source='article.title', read_only=True)

    class Meta:
        model = ValidationHistory
        fields = [
            'id', 'article', 'article_title',
            'word_count', 'target_quartile',
            'validation_score', 'validation_summary',
            'validation_results', 'validated_at'
        ]
        read_only_fields = ['id', 'article_title', 'validated_at']


class QuartileDataSerializer(serializers.Serializer):
    """
    Serializer for returning specific quartile data.
    """

    quartile = serializers.ChoiceField(choices=['Q1', 'Q2', 'Q3', 'Q4'])
    keywords = serializers.DictField()
    structure = serializers.DictField()
