import re
import uuid

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()


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
            if not base_username:  # If email contained only special chars
                base_username = f"user{uuid.uuid4().hex[:8]}"
            username = base_username

            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user.username = username

        return user
