"""
Django Views for SEO Content Validator API
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.files.base import ContentFile

from .models import Guideline, Article, ValidationHistory
from .serializers import (
    GuidelineSerializer,
    GuidelineListSerializer,
    GuidelineUploadSerializer,
    ArticleSerializer,
    ArticleCreateSerializer,
    ArticleValidateSerializer,
    ValidationHistorySerializer,
    QuartileDataSerializer
)
from guideline_storage import GuidelinePreprocessor
from fast_validator import FastArticleValidator

import logging

logger = logging.getLogger(__name__)


class GuidelineViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Guideline CRUD operations.

    Endpoints:
    - GET /api/guidelines/ - List all guidelines
    - POST /api/guidelines/ - Create guideline (not used, use upload instead)
    - GET /api/guidelines/{id}/ - Retrieve guideline details
    - PUT /api/guidelines/{id}/ - Update guideline
    - DELETE /api/guidelines/{id}/ - Delete guideline
    - POST /api/guidelines/upload/ - Upload guideline file and process
    - GET /api/guidelines/{id}/quartile/ - Get specific quartile data
    """

    queryset = Guideline.objects.all()
    serializer_class = GuidelineSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Use lightweight serializer for list action"""
        if self.action == 'list':
            return GuidelineListSerializer
        return GuidelineSerializer

    def get_queryset(self):
        """Filter guidelines by user if not staff"""
        queryset = super().get_queryset()

        # Staff can see all, others only see their own
        if not self.request.user.is_staff:
            queryset = queryset.filter(created_by=self.request.user)

        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by active
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        """
        Upload and process guideline file.

        POST /api/guidelines/upload/
        Content-Type: multipart/form-data

        Body:
            name: Guideline name
            file: .txt file with guideline content

        Returns:
            Guideline object with pre-computed Q1/Q2/Q3/Q4 data
        """
        serializer = GuidelineUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data['name']
        uploaded_file = serializer.validated_data['file']

        # Create Guideline object
        guideline = Guideline.objects.create(
            name=name,
            created_by=request.user,
            original_filename=uploaded_file.name,
            status='processing'
        )

        # Save original file to S3
        guideline.original_file.save(uploaded_file.name, uploaded_file, save=True)

        try:
            # Read file content
            uploaded_file.seek(0)  # Reset file pointer
            file_content = uploaded_file.read().decode('utf-8')

            # Process guideline using GuidelinePreprocessor
            logger.info(f"Processing guideline {guideline.id}: {name}")

            preprocessor = GuidelinePreprocessor()
            stored = preprocessor.process_guideline(
                guideline_source=file_content,
                guideline_name=name,
                guideline_id=str(guideline.id)
            )

            # Update guideline with processed data
            guideline.paragraphs_min = stored.paragraphs_min
            guideline.paragraphs_max = stored.paragraphs_max
            guideline.images_min = stored.images_min
            guideline.images_max = stored.images_max
            guideline.headings_min = stored.headings_min
            guideline.headings_max = stored.headings_max
            guideline.characters_min = stored.characters_min
            guideline.characters_max = stored.characters_max
            guideline.words_min = stored.words_min
            guideline.words_max = stored.words_max
            guideline.keywords_q1 = stored.keywords_q1
            guideline.keywords_q2 = stored.keywords_q2
            guideline.keywords_q3 = stored.keywords_q3
            guideline.keywords_q4 = stored.keywords_q4
            guideline.other_terms = stored.other_terms
            guideline.questions = stored.questions
            guideline.notes = stored.notes
            guideline.total_keywords = len(stored.keywords_q3)
            guideline.status = 'completed'
            guideline.save()

            logger.info(f"Successfully processed guideline {guideline.id}")

            # Return serialized guideline
            return Response(
                GuidelineSerializer(guideline, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"Error processing guideline {guideline.id}: {str(e)}")

            # Update status to failed
            guideline.status = 'failed'
            guideline.error_message = str(e)
            guideline.save()

            return Response(
                {'error': f"Failed to process guideline: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def quartile(self, request, pk=None):
        """
        Get specific quartile data for a guideline.

        GET /api/guidelines/{id}/quartile/?q=Q3

        Query Params:
            q: Quartile (Q1, Q2, Q3, or Q4) - default Q3

        Returns:
            Quartile-specific keyword targets and structure requirements
        """
        guideline = self.get_object()
        quartile_param = request.query_params.get('q', 'Q3').upper()

        if quartile_param not in ['Q1', 'Q2', 'Q3', 'Q4']:
            return Response(
                {'error': 'Invalid quartile. Use Q1, Q2, Q3, or Q4'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get quartile data
        keywords = guideline.get_quartile_data(quartile_param)

        # Structure data
        structure = {
            'paragraphs': {'min': guideline.paragraphs_min, 'max': guideline.paragraphs_max},
            'images': {'min': guideline.images_min, 'max': guideline.images_max},
            'headings': {'min': guideline.headings_min, 'max': guideline.headings_max},
            'characters': {'min': guideline.characters_min, 'max': guideline.characters_max},
            'words': {'min': guideline.words_min, 'max': guideline.words_max},
        }

        data = {
            'quartile': quartile_param,
            'keywords': keywords,
            'structure': structure
        }

        serializer = QuartileDataSerializer(data)
        return Response(serializer.data)


class ArticleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Article CRUD operations.

    Endpoints:
    - GET /api/articles/ - List articles
    - POST /api/articles/ - Create article
    - GET /api/articles/{id}/ - Retrieve article
    - PUT /api/articles/{id}/ - Update article
    - DELETE /api/articles/{id}/ - Delete article
    - POST /api/articles/{id}/validate/ - Validate article
    - POST /api/articles/validate_content/ - Validate content without saving
    """

    queryset = Article.objects.select_related('guideline', 'created_by').all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Use appropriate serializer based on action"""
        if self.action == 'create':
            return ArticleCreateSerializer
        return ArticleSerializer

    def get_queryset(self):
        """Filter articles by user if not staff"""
        queryset = super().get_queryset()

        # Staff can see all, others only see their own
        if not self.request.user.is_staff:
            queryset = queryset.filter(created_by=self.request.user)

        # Filter by guideline
        guideline_id = self.request.query_params.get('guideline')
        if guideline_id:
            queryset = queryset.filter(guideline_id=guideline_id)

        # Filter by published status
        is_published = self.request.query_params.get('is_published')
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')

        return queryset

    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Validate an article.

        POST /api/articles/{id}/validate/

        Body (optional):
            force: true/false - force re-validation even if recently validated

        Returns:
            Validation results with score, feedback, and recommendations
        """
        article = self.get_object()
        force = request.data.get('force', False)

        # Validate article
        try:
            results = article.validate(force=force)

            return Response({
                'article_id': str(article.id),
                'validation_score': article.validation_score,
                'validation_summary': article.validation_summary,
                'validated_at': article.last_validated_at,
                'results': results
            })

        except Exception as e:
            logger.error(f"Error validating article {article.id}: {str(e)}")
            return Response(
                {'error': f"Validation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def validate_content(self, request):
        """
        Validate content without saving as an article.

        POST /api/articles/validate_content/

        Body:
            content: Article content to validate
            guideline_id: UUID of guideline
            target_quartile: Q1, Q2, Q3, or Q4 (default: Q3)

        Returns:
            Validation results
        """
        serializer = ArticleValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content = serializer.validated_data['content']
        guideline_id = serializer.validated_data['guideline_id']
        target_quartile = serializer.validated_data['target_quartile']

        # Get guideline
        guideline = get_object_or_404(Guideline, id=guideline_id, status='completed')

        # Validate
        try:
            stored_guideline = guideline.to_stored_guideline()
            validator = FastArticleValidator(stored_guideline, target_quartile=target_quartile)
            result = validator.validate(content)

            return Response(result.to_dict())

        except Exception as e:
            logger.error(f"Error validating content: {str(e)}")
            return Response(
                {'error': f"Validation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ValidationHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ValidationHistory (read-only).

    Endpoints:
    - GET /api/validation-history/ - List validation history
    - GET /api/validation-history/{id}/ - Retrieve specific validation
    """

    queryset = ValidationHistory.objects.select_related('article').all()
    serializer_class = ValidationHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter by article if specified"""
        queryset = super().get_queryset()

        article_id = self.request.query_params.get('article')
        if article_id:
            queryset = queryset.filter(article_id=article_id)

        return queryset
