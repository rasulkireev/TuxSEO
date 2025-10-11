import json


def before_send(event, hint):
    """
    Sentry before_send hook that filters out JSON-formatted log events.

    This prevents structured log messages (typically from structlog) from being
    sent to Sentry, reducing noise and focusing on actual errors and exceptions.
    """
    if "logentry" not in event:
        return event

    log_entry = event.get("logentry", {})
    message = log_entry.get("message", "")

    if not message:
        return event

    try:
        json.loads(message)
        return None
    except (json.JSONDecodeError, TypeError):
        return event
