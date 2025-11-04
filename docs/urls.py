from django.urls import path

from docs.views import docs_page_view

urlpatterns = [
    path("<str:category>/<str:page>/", docs_page_view, name="docs_page"),
]
