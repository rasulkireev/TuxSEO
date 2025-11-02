import time
from urllib.parse import urlencode

import stripe
from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation
from allauth.account.views import SignupView
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin

User = get_user_model()
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Prefetch, Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DeleteView, DetailView, ListView, TemplateView, UpdateView
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
    ProfileStateTransition,
    Project,
)
from core.tasks import (
    track_event,
    try_create_posthog_alias,
)
from core.utils import get_project_keywords_dict
from tuxseo.utils import get_tuxseo_logger

stripe.api_key = settings.STRIPE_SECRET_KEY


logger = get_tuxseo_logger(__name__)


class LandingView(TemplateView):
    template_name = "pages/landing.html"


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        welcome_status = self.request.GET.get("welcome")
        if welcome_status == "true":
            context["show_onboarding_modal"] = True
            context["show_confetti"] = True

        payment_status = self.request.GET.get("payment")
        if payment_status == "success":
            messages.success(self.request, "Thanks for subscribing, I hope you enjoy the app!")
            context["show_confetti"] = True
        elif payment_status == "failed":
            messages.error(self.request, "Something went wrong with the payment.")

        context["form"] = ProjectScanForm()

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


class AdminPanelView(LoginRequiredMixin, TemplateView):
    template_name = "pages/admin_panel.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "You don't have permission to access the admin panel.")
            return redirect(reverse("home"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        total_users = User.objects.count()
        verified_users = (
            EmailAddress.objects.filter(verified=True).values("user").distinct().count()
        )

        total_projects = Project.objects.count()
        total_blog_posts = GeneratedBlogPost.objects.count()
        posted_blog_posts = GeneratedBlogPost.objects.filter(posted=True).count()

        paid_subscribers = (
            Profile.objects.filter(product__isnull=False).exclude(product__name="Free").count()
        )

        recent_users_data = User.objects.select_related("profile").order_by("-date_joined")[:5]
        recent_users = []
        for user in recent_users_data:
            email_address = EmailAddress.objects.filter(user=user, email=user.email).first()
            recent_users.append(
                {
                    "username": user.username,
                    "email": user.email,
                    "date_joined": user.date_joined,
                    "is_verified": email_address.verified if email_address else False,
                }
            )

        recent_projects = Project.objects.select_related("profile__user").order_by("-created_at")[
            :5
        ]

        context["stats"] = {
            "total_users": total_users,
            "verified_users": verified_users,
            "total_projects": total_projects,
            "total_blog_posts": total_blog_posts,
            "posted_blog_posts": posted_blog_posts,
            "paid_subscribers": paid_subscribers,
            "recent_users": recent_users,
            "recent_projects": recent_projects,
        }

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

    def get_success_url(self):
        success_url = super().get_success_url() or reverse("home")
        welcome_params = {"welcome": "true"}
        return f"{success_url}?{urlencode(welcome_params)}"


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
        context["has_pro_subscription"] = user.profile.is_on_pro_plan

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


class PrivacyPolicyView(TemplateView):
    template_name = "pages/privacy_policy.html"


class TermsOfServiceView(TemplateView):
    template_name = "pages/terms_of_service.html"


@login_required
def create_checkout_session(request, product_name):
    """Create a new subscription checkout session for users without active subscriptions."""
    user = request.user
    profile = user.profile

    # Superusers already have subscription access
    if user.is_superuser:
        logger.warning(
            "[CreateCheckout] Superuser attempted to create checkout session",
            user_id=user.id,
        )
        messages.info(request, "Superusers already have full access.")
        return redirect(reverse("home"))

    try:
        price = djstripe_models.Price.objects.select_related("product").get(
            product__name=product_name, livemode=settings.STRIPE_LIVE_MODE
        )
    except djstripe_models.Price.DoesNotExist:
        logger.error(
            "[CreateCheckout] Price not found",
            user_id=user.id,
            product_name=product_name,
        )
        messages.error(request, "Product not found. Please contact support.")
        return redirect(reverse("home"))

    # Get or create customer
    customer, _ = djstripe_models.Customer.get_or_create(subscriber=user)

    if not profile.customer:
        profile.customer = customer
        profile.save(update_fields=["customer"])

    # Check if user already has an active subscription
    if profile.subscription:
        logger.warning(
            "[CreateCheckout] User already has active subscription",
            user_id=user.id,
            subscription_id=profile.subscription.id,
        )
        messages.info(
            request,
            "You already have an active subscription. Use the upgrade option to change plans.",
        )
        return redirect(reverse("home"))

    # Create checkout session
    logger.info(
        "[CreateCheckout] Creating new checkout session",
        user_id=user.id,
        profile_id=profile.id,
        product_name=product_name,
    )

    base_success_url = request.build_absolute_uri(reverse("home"))
    base_cancel_url = request.build_absolute_uri(reverse("home"))

    success_url = f"{base_success_url}?{urlencode({'payment': 'success'})}"
    cancel_url = f"{base_cancel_url}?{urlencode({'payment': 'cancelled'})}"

    try:
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
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_update={
                "address": "auto",
            },
            subscription_data={
                "metadata": {
                    "user_id": user.id,
                    "profile_id": profile.id,
                    "product_name": product_name,
                }
            },
            metadata={
                "user_id": user.id,
                "profile_id": profile.id,
                "price_id": price.id,
                "action": "new_subscription",
            },
            client_reference_id=f"user_{user.id}_profile_{profile.id}_{int(time.time())}",
        )

        logger.info(
            "[CreateCheckout] Created checkout session",
            user_id=user.id,
            profile_id=profile.id,
            product_name=product_name,
            checkout_session_id=checkout_session.id,
        )

        return redirect(checkout_session.url, code=303)

    except stripe.error.StripeError as e:
        logger.error(
            "[CreateCheckout] Stripe error creating checkout session",
            user_id=user.id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        messages.error(request, "Unable to create checkout session. Please try again.")
        return redirect(reverse("home"))


@login_required
def upgrade_subscription(request, product_name):
    """Upgrade or downgrade an existing active subscription."""
    user = request.user
    profile = user.profile

    # Superusers already have full access
    if user.is_superuser:
        logger.warning(
            "[UpgradeSubscription] Superuser attempted to upgrade subscription",
            user_id=user.id,
        )
        messages.info(request, "Superusers already have full access.")
        return redirect(reverse("home"))

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect(reverse("home"))

    try:
        new_price = djstripe_models.Price.objects.select_related("product").get(
            product__name=product_name, livemode=settings.STRIPE_LIVE_MODE
        )
    except djstripe_models.Price.DoesNotExist:
        logger.error(
            "[UpgradeSubscription] Price not found",
            user_id=user.id,
            product_name=product_name,
        )
        messages.error(request, "Product not found. Please contact support.")
        return redirect(reverse("home"))

    active_subscription = profile.subscription

    if not active_subscription:
        logger.warning(
            "[UpgradeSubscription] No active subscription found",
            user_id=user.id,
            profile_id=profile.id,
        )
        messages.error(request, "No active subscription found. Please create a new subscription.")
        return redirect(reverse("home"))

    logger.info(
        "[UpgradeSubscription] Processing subscription change",
        user_id=user.id,
        profile_id=profile.id,
        subscription_id=active_subscription.id,
        new_product_name=product_name,
    )

    try:
        # Get current subscription item
        subscription_item = active_subscription.items.first()

        if not subscription_item:
            logger.error(
                "[UpgradeSubscription] No subscription items found",
                user_id=user.id,
                subscription_id=active_subscription.id,
            )
            messages.error(request, "Unable to modify subscription. Please contact support.")
            return redirect(reverse("home"))

        current_price = subscription_item.price
        current_product = current_price.product

        # Check if already on this plan
        if current_price.id == new_price.id:
            messages.info(request, f"You are already subscribed to {product_name}.")
            return redirect(reverse("home"))

        # Determine if upgrade or downgrade based on unit amount
        current_amount = current_price.unit_amount or 0
        new_amount = new_price.unit_amount or 0
        is_upgrade = new_amount > current_amount
        action_type = "upgrade" if is_upgrade else "downgrade"

        # Update the subscription
        updated_subscription = stripe.Subscription.modify(
            active_subscription.id,
            items=[
                {
                    "id": subscription_item.id,
                    "price": new_price.id,
                }
            ],
            proration_behavior="create_prorations",
            metadata={
                "user_id": user.id,
                "profile_id": profile.id,
                "action": action_type,
                "from_product": current_product.name,
                "to_product": product_name,
            },
        )

        # Sync with dj-stripe
        synced_subscription = djstripe_models.Subscription.sync_from_stripe_data(
            updated_subscription
        )

        # Update profile
        profile.subscription = synced_subscription
        profile.product = new_price.product
        profile.save(update_fields=["subscription", "product", "updated_at"])

        # Log state transition
        ProfileStateTransition.objects.create(
            profile=profile,
            from_state=profile.state if hasattr(profile, "state") else "active",
            to_state="active",
            backup_profile_id=profile.id,
            metadata={
                "action": f"subscription_{action_type}",
                "from_product": current_product.name,
                "from_price_id": current_price.id,
                "to_product": product_name,
                "to_price_id": new_price.id,
                "subscription_id": synced_subscription.id,
            },
        )

        action_word = "upgraded" if is_upgrade else "changed"
        messages.success(request, f"Successfully {action_word} to {product_name}!")

        logger.info(
            "[UpgradeSubscription] Successfully modified subscription",
            user_id=user.id,
            profile_id=profile.id,
            subscription_id=synced_subscription.id,
            action=action_type,
            from_product=current_product.name,
            to_product=product_name,
        )

        return redirect(reverse("home") + "?payment=success")

    except stripe.error.StripeError as e:
        logger.error(
            "[UpgradeSubscription] Stripe error",
            user_id=user.id,
            subscription_id=active_subscription.id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        messages.error(
            request, "Unable to modify subscription. Please try again or contact support."
        )
        return redirect(reverse("home"))


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
        profile = self.request.user.profile

        # Use a single query with annotation to count posted blog posts
        all_suggestions = project.blog_post_title_suggestions.annotate(
            posted_count=Count("generated_blog_posts", filter=Q(generated_blog_posts__posted=True))
        ).prefetch_related("generated_blog_posts")

        # Get all project keywords with their usage status for quick lookup
        project_keywords = get_project_keywords_dict(project)

        # Categorize suggestions based on the annotated posted_count
        posted_suggestions = []
        archived_suggestions = []
        active_suggestions = []

        for suggestion in all_suggestions:
            has_posted = suggestion.posted_count > 0

            # Add keyword usage info to each suggestion
            suggestion.keywords_with_usage = []
            if suggestion.target_keywords:
                for keyword_text in suggestion.target_keywords:
                    keyword_info = project_keywords.get(
                        keyword_text.lower(),
                        {"keyword": None, "in_use": False, "project_keyword_id": None},
                    )
                    suggestion.keywords_with_usage.append(
                        {
                            "text": keyword_text,
                            "keyword": keyword_info["keyword"],
                            "in_use": keyword_info["in_use"],
                            "project_keyword_id": keyword_info["project_keyword_id"],
                        }
                    )

            if has_posted:
                posted_suggestions.append(suggestion)
            elif suggestion.archived:
                archived_suggestions.append(suggestion)
            else:
                active_suggestions.append(suggestion)

        context["posted_suggestions"] = posted_suggestions
        context["archived_suggestions"] = archived_suggestions
        context["active_suggestions"] = active_suggestions

        context["has_pro_subscription"] = profile.is_on_pro_plan
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


class ProjectPagesView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "project/project_pages.html"
    context_object_name = "project"

    def get_queryset(self):
        # Ensure users can only see their own projects
        return Project.objects.filter(profile=self.request.user.profile)

    def get_context_data(self, **kwargs):
        from urllib.parse import urlparse

        context = super().get_context_data(**kwargs)
        project = self.object

        # Parse the project base URL to get the domain
        project_parsed_url = urlparse(project.url)
        project_base_url = f"{project_parsed_url.scheme}://{project_parsed_url.netloc}"

        # Get all pages for this project, ordered by analyzed status and creation date
        all_project_pages = project.project_pages.order_by("-date_analyzed", "-created_at")

        # Filter to only show internal pages (same domain as project)
        filtered_pages = []
        for page in all_project_pages:
            page_parsed_url = urlparse(page.url)
            page_base_url = f"{page_parsed_url.scheme}://{page_parsed_url.netloc}"

            # Only include pages that match the project's base URL
            if page_base_url == project_base_url:
                # Add the path for display purposes
                page.url_path = page_parsed_url.path or "/"
                filtered_pages.append(page)

        # Calculate statistics (based on filtered pages)
        total_pages_count = len(filtered_pages)
        analyzed_pages_count = sum(1 for page in filtered_pages if page.date_analyzed)
        ai_pages_count = sum(1 for page in filtered_pages if page.source == "AI")
        sitemap_pages_count = sum(1 for page in filtered_pages if page.source == "SITEMAP")

        context["pages"] = filtered_pages
        context["project_base_url"] = project_base_url
        context["total_pages_count"] = total_pages_count
        context["analyzed_pages_count"] = analyzed_pages_count
        context["ai_pages_count"] = ai_pages_count
        context["sitemap_pages_count"] = sitemap_pages_count
        context["unanalyzed_pages_count"] = total_pages_count - analyzed_pages_count

        return context


class GeneratedBlogPostDetailView(LoginRequiredMixin, DetailView):
    model = GeneratedBlogPost
    template_name = "blog/generated_blog_post_detail.html"
    context_object_name = "generated_post"

    def get_queryset(self):
        return GeneratedBlogPost.objects.filter(
            project__profile=self.request.user.profile, project__pk=self.kwargs["project_pk"]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        generated_post = self.object
        project = generated_post.project
        profile = self.request.user.profile

        context["project"] = project
        context["has_pro_subscription"] = profile.is_on_pro_plan
        context["has_auto_submission_setting"] = AutoSubmissionSetting.objects.filter(
            project=project
        ).exists()

        # Add keyword usage info to the title suggestion
        if generated_post.title:
            # Get all project keywords with their usage status for quick lookup
            project_keywords = get_project_keywords_dict(project)

            # Add keyword usage info to the suggestion
            generated_post.title.keywords_with_usage = []
            if generated_post.title.target_keywords:
                for keyword_text in generated_post.title.target_keywords:
                    keyword_info = project_keywords.get(
                        keyword_text.lower(),
                        {"keyword": None, "in_use": False, "project_keyword_id": None},
                    )
                    generated_post.title.keywords_with_usage.append(
                        {
                            "text": keyword_text,
                            "keyword": keyword_info["keyword"],
                            "in_use": keyword_info["in_use"],
                            "project_keyword_id": keyword_info["project_keyword_id"],
                        }
                    )

        return context


@login_required
def download_blog_post_pdf(request, project_pk, pk):
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from weasyprint import HTML
    
    generated_post = GeneratedBlogPost.objects.filter(
        project__profile=request.user.profile, 
        project__pk=project_pk,
        pk=pk
    ).first()
    
    if not generated_post:
        messages.error(request, "Blog post not found.")
        return redirect("home")
    
    html_content = render_to_string(
        "blog/generated_blog_post_pdf.html",
        {
            "generated_post": generated_post,
            "project": generated_post.project,
        }
    )
    
    pdf_file = HTML(string=html_content).write_pdf()
    
    response = HttpResponse(pdf_file, content_type="application/pdf")
    filename = f"{generated_post.slug}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    
    logger.info(
        "PDF downloaded for blog post",
        blog_post_id=generated_post.id,
        project_id=generated_post.project.id,
        user_id=request.user.id,
    )
    
    return response


class PublishHistoryView(LoginRequiredMixin, DetailView):
    login_url = "account_login"
    model = Project
    template_name = "project/project_publish_history.html"
    context_object_name = "project"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object

        published_posts = (
            GeneratedBlogPost.objects.filter(project=project, posted=True)
            .select_related("title")
            .order_by("-date_posted", "-updated_at")
        )

        context["published_posts"] = published_posts
        context["total_published_count"] = published_posts.count()

        return context


class ProjectDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    login_url = "account_login"
    model = Project
    success_url = reverse_lazy("home")
    success_message = "Project deleted successfully"

    def get_queryset(self):
        return Project.objects.filter(profile=self.request.user.profile)

    def form_valid(self, form):
        project_name = self.object.name or self.object.url

        async_task(
            track_event,
            profile_id=self.request.user.profile.id,
            event_name="project_deleted",
            properties={
                "project_id": self.object.id,
                "project_name": project_name,
            },
            source_function="ProjectDeleteView - form_valid",
            group="Track Event",
        )

        return super().form_valid(form)


def trigger_error(request):
    try:
        foo = 1 / 0
    except ZeroDivisionError as e:
        logger.exception("[TriggerError] Triggering zero division error", error=str(e), foo="bar")

    try:
        raise Exception("This is a test error")
    except Exception as e:
        raise e

    return foo
