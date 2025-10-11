import json

from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


def before_send(event, hint):
    """
    Drop log events from django_structlog.middlewares.request and JSON-formatted logs.
    """
    # Check if this is a log message event (not an exception)
    logentry = event.get("logentry")
    if logentry:
        logger.info("[BeforeSend] logentry", logentry=logentry)
        message = logentry.get("message", "")
        logger_name = event.get("logger", "")

        # Drop django_structlog middleware request_failed logs
        if logger_name == "django_structlog.middlewares.request" and "request_failed" in message:
            logger.info("[BeforeSend] Dropping request_failed log", logentry=logentry)
            return None  # Drop this event

        # Try to parse the message as JSON
        try:
            # If parsing succeeds and it's a dict or list, drop the event
            parsed = json.loads(message)
            if isinstance(parsed, dict | list):
                logger.info("[BeforeSend] Dropping JSON log", logentry=logentry)
                return None  # Drop this event, do not send to Sentry
        except (json.JSONDecodeError, TypeError):
            # Not JSON, allow event to be sent
            pass

    return event
