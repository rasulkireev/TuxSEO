import posthog
from django.apps import AppConfig
from django.conf import settings

from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        import core.signals  # noqa
        import core.webhooks  # noqa

        if settings.POSTHOG_API_KEY:
            posthog.api_key = settings.POSTHOG_API_KEY
            posthog.host = "https://us.i.posthog.com"

            if settings.ENVIRONMENT == "dev":
                posthog.debug = True
