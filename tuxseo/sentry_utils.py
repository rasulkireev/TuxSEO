from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


def before_send(event, hint):
    print("=" * 50)
    print("SENTRY BEFORE_SEND CALLED")
    print("=" * 50)

    # Print event structure
    print("\n[EVENT]")
    print(event)

    # Print hint structure
    print("\n[HINT]")
    print(hint)

    return event
