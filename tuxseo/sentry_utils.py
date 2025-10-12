from tuxseo.utils import get_tuxseo_logger

logger = get_tuxseo_logger(__name__)


def before_send(event, hint):
    logger.info("[BeforeSend] Event", event=event, hint=hint)

    return event
