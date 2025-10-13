from logging import LogRecord

from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.types import Event, Hint

_IGNORED_LOGGERS = {"django_structlog.middlewares.request"}


def ignore_logger(logger_name: str) -> None:
    _IGNORED_LOGGERS.add(logger_name)


class CustomLoggingIntegration(LoggingIntegration):
    def _handle_record(self, record: LogRecord) -> None:
        # This match upper logger names, e.g. "celery" will match "celery.worker"
        # or "celery.worker.job"
        if record.name in _IGNORED_LOGGERS or record.name.split(".")[0] in _IGNORED_LOGGERS:
            return
        super()._handle_record(record)


def before_send(event: Event, hint: Hint) -> Event | None:
    # Filter out all ZeroDivisionError events.
    # Note that the exception type is available in the hint,
    # but we should handle the case where the exception info
    # is missing.
    # if hint.get("exc_info", [None])[0] == ZeroDivisionError:
    #     return None

    # We can set extra data on the event's "extra" field.
    if "extra" not in event:
        event["extra"] = {"foo-foo-foo": "bar-bar-bar"}
    event["extra"]["foo-foo"] = "bar-bar"

    event["tags"].append(["Test Tag", "Hello"])
    # We have modified the event as desired, so return the event.
    # The SDK will then send the returned event to Sentry.
    return event
