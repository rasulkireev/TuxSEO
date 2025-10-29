from allauth.account.signals import email_confirmed, user_signed_up
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django_q.tasks import async_task

from core.models import Profile, ProfileStates, Project
from core.tasks import add_email_to_buttondown
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile = Profile.objects.create(user=instance)
        profile.track_state_change(
            to_state=ProfileStates.SIGNED_UP,
        )

    if instance.id == 1:
        # Use update() to avoid triggering the signal again
        User.objects.filter(id=1).update(is_staff=True, is_superuser=True)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, "profile"):
        instance.profile.save()


@receiver(email_confirmed)
def add_email_to_buttondown_on_confirm(sender, **kwargs):
    logger.info(
        "Adding new user to buttondown newsletter, on email confirmation",
        kwargs=kwargs,
        sender=sender,
    )
    async_task(add_email_to_buttondown, kwargs["email_address"], tag="user")


@receiver(user_signed_up)
def email_confirmation_callback(sender, request, user, **kwargs):
    if "sociallogin" in kwargs:
        logger.info(
            "Adding new user to buttondown newsletter on social signup",
            kwargs=kwargs,
            sender=sender,
        )
        email = kwargs["sociallogin"].user.email
        if email:
            async_task(add_email_to_buttondown, email, tag="user")


@receiver(post_save, sender=Project)
def parse_sitemap_on_save(sender, instance, created, **kwargs):
    """
    When a project is saved with a sitemap_url, parse the sitemap and save URLs.
    Uses update_fields to check if sitemap_url was specifically updated.
    """
    update_fields = kwargs.get("update_fields")

    # Check if sitemap_url was just set or updated
    if instance.sitemap_url:
        # If update_fields is None, all fields were saved
        # If update_fields contains 'sitemap_url', it was explicitly updated
        should_parse = False

        if created and instance.sitemap_url:
            should_parse = True
        elif update_fields is None:
            # All fields updated, check if sitemap_url changed
            try:
                old_instance = Project.objects.get(pk=instance.pk)
                if old_instance.sitemap_url != instance.sitemap_url:
                    should_parse = True
            except Project.DoesNotExist:
                should_parse = True
        elif update_fields and "sitemap_url" in update_fields:
            should_parse = True

        if should_parse:
            logger.info(
                "[Parse Sitemap Signal] Scheduling sitemap parsing",
                project_id=instance.id,
                project_name=instance.name,
                sitemap_url=instance.sitemap_url,
            )
            async_task(
                "core.tasks.parse_sitemap_and_save_urls",
                instance.id,
                group="Parse Sitemap",
            )
