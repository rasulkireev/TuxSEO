from django.urls import path

from core import views
from core.api.views import api

urlpatterns = [
    # pages
    path("", views.HomeView.as_view(), name="home"),
    path("settings", views.UserSettingsView.as_view(), name="settings"),
    path("privacy-policy", views.PrivacyPolicyView.as_view(), name="privacy_policy"),
    path("terms-of-service", views.TermsOfServiceView.as_view(), name="terms_of_service"),
    # blog
    path("blog/", views.BlogView.as_view(), name="blog_posts"),
    path("blog/<slug:slug>", views.BlogPostView.as_view(), name="blog_post"),
    # app
    path("api/", api.urls),
    path("project/<int:pk>/", views.ProjectDetailView.as_view(), name="project_detail"),
    path(
        "project/<int:pk>/settings/", views.ProjectSettingsView.as_view(), name="project_settings"
    ),
    path(
        "project/<int:pk>/keywords/", views.ProjectKeywordsView.as_view(), name="project_keywords"
    ),
    path(
        "project/<int:pk>/publish-history",
        views.PublishHistoryView.as_view(),
        name="publish_history",
    ),
    path("project/<int:pk>/delete/", views.ProjectDeleteView.as_view(), name="project_delete"),
    path(
        "project/<int:project_pk>/post/<int:pk>/",
        views.GeneratedBlogPostDetailView.as_view(),
        name="generated_blog_post_detail",
    ),
    # utils
    path("resend-confirmation/", views.resend_confirmation_email, name="resend_confirmation"),
    # payments
    path("pricing", views.PricingView.as_view(), name="pricing"),
    path(
        "create-checkout-session/<int:pk>/<str:product_name>/",
        views.create_checkout_session,
        name="user_upgrade_checkout_session",
    ),
    path(
        "create-customer-portal/",
        views.create_customer_portal_session,
        name="create_customer_portal_session",
    ),
]
