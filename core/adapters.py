import re

import structlog
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()
logger = structlog.get_logger(__name__)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to automatically generate usernames from email addresses
    during social authentication signup, bypassing the username selection page.
    """

    def is_auto_signup_allowed(self, request, sociallogin):
        """
        Allow automatic signup without showing the signup form.
        This bypasses the confirmation page entirely.
        """
        # Ensure we have an email before allowing auto signup
        email = sociallogin.account.extra_data.get("email")
        if not email:
            logger.warning(
                "Social signup blocked - no email provided", provider=sociallogin.account.provider
            )
            return False

        return True

    def pre_social_login(self, request, sociallogin):
        """
        Connect to existing user account if email matches.
        This prevents duplicate accounts for the same email.
        """
        if sociallogin.is_existing:
            return

        try:
            email = sociallogin.account.extra_data.get("email", "").lower()
            if email:
                user = User.objects.get(email__iexact=email)
                # Connect the social account to the existing user
                sociallogin.connect(request, user)
                logger.info(
                    "Connected social account to existing user",
                    email=email,
                    provider=sociallogin.account.provider,
                )
        except User.DoesNotExist:
            pass
        except User.MultipleObjectsReturned:
            logger.error("Multiple users found with same email", email=email)
            pass

    def populate_user(self, request, sociallogin, data):
        """
        Automatically set username from email address before user creation.
        Uses the part before @ symbol as username, ensuring uniqueness.
        """
        user = super().populate_user(request, sociallogin, data)

        if not user.username and user.email:
            # Clean the email prefix to make it a valid username
            base_username = user.email.split("@")[0]
            # Remove any non-alphanumeric characters except underscores
            base_username = re.sub(r"[^\w]", "", base_username)

            # Ensure it's not empty after cleaning
            if not base_username:
                base_username = "user"

            # Make it lowercase for consistency
            base_username = base_username.lower()
            username = base_username

            # Ensure uniqueness
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user.username = username

            logger.info(
                "Auto-generated username for social signup",
                email=user.email,
                username=username,
                provider=sociallogin.account.provider,
            )

        return user

    def save_user(self, request, sociallogin, form=None):
        """
        Save the user and ensure username is set.
        This is called after populate_user.
        """
        user = super().save_user(request, sociallogin, form)

        # Double-check username exists (safety net)
        if not user.username:
            user.username = f"user_{user.id}"
            user.save(update_fields=["username"])
            logger.warning("Had to set emergency username", user_id=user.id, username=user.username)

        return user
