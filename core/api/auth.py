import logging

from django.http import HttpRequest
from ninja.security import APIKeyQuery

from core.models import Profile

logger = logging.getLogger(__name__)


class APIKeyAuth(APIKeyQuery):
    param_name = "api_key"

    def authenticate(self, request: HttpRequest, key: str) -> Profile | None:
        try:
            return Profile.objects.get(key=key)
        except Profile.DoesNotExist:
            logger.warning(
                "[Django Ninja Auth] Invalid API key",
                extra={
                    "key": key,
                },
            )
            return None


class SessionAuth:
    """Authentication via Django session"""

    def authenticate(self, request: HttpRequest) -> Profile | None:
        if hasattr(request, "user") and request.user.is_authenticated:
            try:
                return request.user.profile
            except Profile.DoesNotExist:
                logger.warning(
                    "[Django Ninja Auth] No profile for user",
                    extra={
                        "user_id": request.user.id,
                    },
                )
                return None
        return None

    def __call__(self, request: HttpRequest):
        return self.authenticate(request)


class SuperuserAPIKeyAuth(APIKeyQuery):
    param_name = "api_key"

    def authenticate(self, request: HttpRequest, key: str) -> Profile | None:
        try:
            profile = Profile.objects.get(key=key)
            if profile.user.is_superuser:
                return profile
            logger.warning(
                "[Django Ninja Auth] Non-superuser attempted admin access",
                extra={
                    "profile_id": profile.user_id,
                },
            )
            return None
        except Profile.DoesNotExist:
            logger.warning("[Django Ninja Auth] Profile does not exist", key=key)
            return None


api_key_auth = APIKeyAuth()
session_auth = SessionAuth()
superuser_api_auth = SuperuserAPIKeyAuth()
