"""
URL Configuration for SEO Content Validator API
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GuidelineViewSet, ArticleViewSet, ValidationHistoryViewSet

# Create router
router = DefaultRouter()
router.register(r'guidelines', GuidelineViewSet, basename='guideline')
router.register(r'articles', ArticleViewSet, basename='article')
router.register(r'validation-history', ValidationHistoryViewSet, basename='validation-history')

app_name = 'seo_validator'

urlpatterns = [
    path('', include(router.urls)),
]

"""
Available Endpoints:

# Guidelines
GET    /api/guidelines/                     - List all guidelines
POST   /api/guidelines/upload/              - Upload guideline file
GET    /api/guidelines/{id}/                - Get guideline details
PUT    /api/guidelines/{id}/                - Update guideline
PATCH  /api/guidelines/{id}/                - Partial update guideline
DELETE /api/guidelines/{id}/                - Delete guideline
GET    /api/guidelines/{id}/quartile/?q=Q3  - Get specific quartile data

# Articles
GET    /api/articles/                       - List articles
POST   /api/articles/                       - Create article
GET    /api/articles/{id}/                  - Get article details
PUT    /api/articles/{id}/                  - Update article
PATCH  /api/articles/{id}/                  - Partial update article
DELETE /api/articles/{id}/                  - Delete article
POST   /api/articles/{id}/validate/         - Validate article
POST   /api/articles/validate_content/      - Validate content without saving

# Validation History
GET    /api/validation-history/             - List validation history
GET    /api/validation-history/{id}/        - Get validation details

Query Parameters:
- /api/guidelines/?status=completed         - Filter by status
- /api/guidelines/?is_active=true           - Filter by active status
- /api/articles/?guideline={uuid}           - Filter by guideline
- /api/articles/?is_published=true          - Filter by published status
- /api/validation-history/?article={uuid}   - Filter by article
"""
