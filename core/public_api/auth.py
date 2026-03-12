from django.http import HttpRequest
from ninja.security import APIKeyHeader

from core.models import Profile
from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


class PublicAPIKeyAuth(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request: HttpRequest, key: str) -> Profile | None:
        try:
            return Profile.objects.get(key=key)
        except Profile.DoesNotExist:
            logger.warning("[Public API Auth] Invalid API key", key=key)
            return None


public_api_key_auth = PublicAPIKeyAuth()
