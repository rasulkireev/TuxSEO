from urllib.parse import urlencode

import stripe
from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation
from allauth.account.views import SignupView
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Prefetch, Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView, TemplateView, UpdateView
from django_q.tasks import async_task
from djstripe import models as djstripe_models

from core.choices import BlogPostStatus, Language, ProfileStates
from core.forms import AutoSubmissionSettingForm, ProfileUpdateForm, ProjectScanForm
from core.models import (
    AutoSubmissionSetting,
    BlogPost,
    GeneratedBlogPost,
    KeywordTrend,
    Profile,
    Project,
)
from core.tasks import track_event, try_create_posthog_alias
from tuxseo.utils import get_tuxseo_logger

stripe.api_key = settings.STRIPE_SECRET_KEY


logger = get_tuxseo_logger(__name__)


class HomeView(TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        payment_status = self.request.GET.get("payment")
        if payment_status == "success":
            messages.success(self.request, "Thanks for subscribing, I hope you enjoy the app!")
            context["show_confetti"] = True
        elif payment_status == "failed":
            messages.error(self.request, "Something went wrong with the payment.")

        context["form"] = ProjectScanForm()

        # Add projects to context for authenticated users
        if self.request.user.is_authenticated:
            user = self.request.user
            profile = user.profile

            projects = (
                Project.objects.filter(profile=profile)
                .annotate(
                    posted_posts_count=Count(
                        "generated_blog_posts", filter=Q(generated_blog_posts__posted=True)
                    )
                )
                .order_by("-created_at")
            )

            # Annotate projects with counts
            projects_with_stats = []
            for project in projects:
                project_stats = {
                    "project": project,
                    "posted_posts_count": project.posted_posts_count,
                }
                projects_with_stats.append(project_stats)

            context["projects"] = projects_with_stats

            email_address = EmailAddress.objects.get_for_user(user, user.email)
            context["email_verified"] = email_address.verified

        return context


class AccountSignupView(SignupView):
    template_name = "account/signup.html"

    def form_valid(self, form):
        response = super().form_valid(form)

        user = self.user
        profile = user.profile

        if settings.POSTHOG_API_KEY:
            async_task(
                try_create_posthog_alias,
                profile_id=profile.id,
                cookies=self.request.COOKIES,
                source_function="AccountSignupView - form_valid",
                group="Create Posthog Alias",
            )

        async_task(
            track_event,
            profile_id=profile.id,
            event_name="user_signed_up",
            properties={
                "$set": {
                    "email": profile.user.email,
                    "username": profile.user.username,
                },
            },
            source_function="AccountSignupView - form_valid",
            group="Track Event",
        )

        return response


class UserSettingsView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    login_url = "account_login"
    model = Profile
    form_class = ProfileUpdateForm
    success_message = "User Profile Updated"
    success_url = reverse_lazy("settings")
    template_name = "pages/user-settings.html"

    def get_object(self):
        return self.request.user.profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        email_address = EmailAddress.objects.get_for_user(user, user.email)
        context["email_verified"] = email_address.verified
        context["resend_confirmation_url"] = reverse("resend_confirmation")
        context["has_subscription"] = user.profile.has_product_or_subscription

        return context


@login_required
def resend_confirmation_email(request):
    user = request.user
    send_email_confirmation(request, user, EmailAddress.objects.get_for_user(user, user.email))

    return redirect("settings")


class PricingView(TemplateView):
    template_name = "pages/pricing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        number_of_subscribed_users = Profile.objects.filter(state=ProfileStates.SUBSCRIBED).count()

        if self.request.user.is_authenticated:
            try:
                profile = self.request.user.profile
                context["has_pro_subscription"] = profile.has_product_or_subscription
            except Profile.DoesNotExist:
                context["has_pro_subscription"] = False
        else:
            context["has_pro_subscription"] = False

        context["early_bird_spots_left"] = 20 - number_of_subscribed_users - 1

        return context


def create_checkout_session(request, pk, plan):
    user = request.user

    price = djstripe_models.Price.objects.get(nickname=plan)
    customer, _ = djstripe_models.Customer.get_or_create(subscriber=user)

    profile = user.profile
    profile.customer = customer
    profile.save(update_fields=["customer"])

    base_success_url = request.build_absolute_uri(reverse("home"))
    base_cancel_url = request.build_absolute_uri(reverse("home"))

    success_params = {"payment": "success"}
    success_url = f"{base_success_url}?{urlencode(success_params)}"

    cancel_params = {"payment": "failed"}
    cancel_url = f"{base_cancel_url}?{urlencode(cancel_params)}"

    checkout_session = stripe.checkout.Session.create(
        customer=customer.id,
        payment_method_types=["card"],
        allow_promotion_codes=True,
        automatic_tax={"enabled": True},
        line_items=[
            {
                "price": price.id,
                "quantity": 1,
            }
        ],
        mode="payment" if "one-time" in plan else "subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_update={
            "address": "auto",
        },
        metadata={"user_id": user.id, "pk": pk, "price_id": price.id},
    )

    return redirect(checkout_session.url, code=303)


@login_required
def create_customer_portal_session(request):
    user = request.user
    customer = djstripe_models.Customer.objects.get(subscriber=user)

    session = stripe.billing_portal.Session.create(
        customer=customer.id,
        return_url=request.build_absolute_uri(reverse("home")),
    )

    return redirect(session.url, code=303)


class BlogView(ListView):
    model = BlogPost
    template_name = "blog/blog_posts.html"
    context_object_name = "blog_posts"

    def get_queryset(self):
        return BlogPost.objects.filter(status=BlogPostStatus.PUBLISHED).order_by("-created_at")


class BlogPostView(DetailView):
    model = BlogPost
    template_name = "blog/blog_post.html"
    context_object_name = "blog_post"


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "project/project_detail.html"
    context_object_name = "project"

    def get_queryset(self):
        # Ensure users can only see their own projects
        return Project.objects.filter(profile=self.request.user.profile)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object

        context["has_content_access"] = self.request.user.profile.has_active_subscription
        context["has_pricing_page"] = project.has_pricing_page

        # Use a single query with annotation to count posted blog posts
        all_suggestions = project.blog_post_title_suggestions.annotate(
            posted_count=Count("generated_blog_posts", filter=Q(generated_blog_posts__posted=True))
        ).prefetch_related("generated_blog_posts")

        # Categorize suggestions based on the annotated posted_count
        posted_suggestions = []
        archived_suggestions = []
        active_suggestions = []

        for suggestion in all_suggestions:
            has_posted = suggestion.posted_count > 0

            if has_posted:
                posted_suggestions.append(suggestion)
            elif suggestion.archived:
                archived_suggestions.append(suggestion)
            else:
                active_suggestions.append(suggestion)

        context["posted_suggestions"] = posted_suggestions
        context["archived_suggestions"] = archived_suggestions
        context["active_suggestions"] = active_suggestions

        context["has_pro_subscription"] = self.request.user.profile.has_active_subscription
        context["has_auto_submission_setting"] = AutoSubmissionSetting.objects.filter(
            project=project
        ).exists()

        return context


class ProjectSettingsView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "project/project_settings.html"
    context_object_name = "project"

    def get_queryset(self):
        # Ensure users can only see their own projects
        return Project.objects.filter(profile=self.request.user.profile)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        # Try to get existing settings for this project
        settings = AutoSubmissionSetting.objects.filter(project=project).first()
        if settings:
            form = AutoSubmissionSettingForm(instance=settings)
        else:
            form = AutoSubmissionSettingForm()
        context["auto_submission_settings_form"] = form
        context["languages"] = Language.choices

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        project = self.object
        settings = AutoSubmissionSetting.objects.filter(project=project).first()
        if settings:
            form = AutoSubmissionSettingForm(request.POST, instance=settings)
        else:
            form = AutoSubmissionSettingForm(request.POST)
        if form.is_valid():
            auto_settings = form.save(commit=False)
            auto_settings.project = project
            auto_settings.save()
            messages.success(request, "Automatic submission settings saved.")
            return redirect("project_settings", pk=project.pk)
        else:
            context = self.get_context_data()
            context["auto_submission_settings_form"] = form
            return self.render_to_response(context)


class ProjectKeywordsView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "project/project_keywords.html"
    context_object_name = "project"

    def get_queryset(self):
        # Ensure users can only see their own projects
        return Project.objects.filter(profile=self.request.user.profile)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object

        # Get all keywords associated with this project with their metrics
        project_keywords = (
            project.project_keywords.select_related("keyword")
            .prefetch_related(
                Prefetch("keyword__trends", queryset=KeywordTrend.objects.order_by("year", "month"))
            )
            .order_by("-keyword__volume", "keyword__keyword_text")
        )

        # Prepare keywords with trend data for the template and calculate counts
        keywords_with_trends = []
        total_keywords_count = 0
        used_keywords_count = 0

        for project_keyword in project_keywords:
            keyword = project_keyword.keyword

            # Get trend data for this keyword
            trend_data = [
                {"month": trend.month, "year": trend.year, "value": trend.value}
                for trend in keyword.trends.all()
            ]

            # Create keyword object with all necessary data
            keyword_data = {
                "id": keyword.id,
                "keyword_text": keyword.keyword_text,
                "volume": keyword.volume,
                "cpc_value": keyword.cpc_value,
                "cpc_currency": keyword.cpc_currency,
                "competition": keyword.competition,
                "created_at": project_keyword.created_at,
                "use": project_keyword.use,
                "trend_data": trend_data,
                "project_keyword_id": project_keyword.id,
            }
            keywords_with_trends.append(keyword_data)

            # Count keywords while we're iterating
            total_keywords_count += 1
            if project_keyword.use:
                used_keywords_count += 1

        context["keywords"] = keywords_with_trends
        context["total_keywords_count"] = total_keywords_count
        context["used_keywords_count"] = used_keywords_count
        context["available_keywords_count"] = total_keywords_count - used_keywords_count

        return context


class GeneratedBlogPostDetailView(LoginRequiredMixin, DetailView):
    model = GeneratedBlogPost
    template_name = "blog/generated_blog_post_detail.html"
    context_object_name = "generated_post"

    def get_queryset(self):
        return GeneratedBlogPost.objects.filter(
            project__profile=self.request.user.profile, project__pk=self.kwargs["project_pk"]
        )
