import re
import uuid

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

from core.choices import EmailType
from core.utils import track_email_sent

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter to track email confirmations and welcome emails.
    """

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """
        Override to track email confirmation sends.
        """
        profile = emailconfirmation.email_address.user.profile if hasattr(
            emailconfirmation.email_address.user, "profile"
        ) else None

        track_email_sent(
            email_address=emailconfirmation.email_address.email,
            email_type=EmailType.EMAIL_CONFIRMATION,
            profile=profile
        )

        return super().send_confirmation_mail(request, emailconfirmation, signup)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to automatically generate usernames from email addresses
    during social authentication signup, bypassing the username selection page.
    """

    def populate_user(self, request, sociallogin, data):
        """
        Automatically set username from email address before user creation.
        Uses the part before @ symbol as username, ensuring uniqueness.
        """
        user = super().populate_user(request, sociallogin, data)

        if not user.username and user.email:
            base_username = re.sub(r"[^\w]", "", user.email.split("@")[0])
            if not base_username:
                base_username = f"user{uuid.uuid4().hex[:8]}"
            username = base_username

            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user.username = username

        return user
