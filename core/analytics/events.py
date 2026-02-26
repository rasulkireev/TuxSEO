import json
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

TAXONOMY_PATH = Path(__file__).with_name("event_taxonomy.json")


@lru_cache(maxsize=1)
def _load_event_taxonomy() -> dict:
    with TAXONOMY_PATH.open(encoding="utf-8") as event_taxonomy_file:
        taxonomy = json.load(event_taxonomy_file)

    if not isinstance(taxonomy, dict) or "events" not in taxonomy:
        raise ValueError("Invalid analytics event taxonomy: missing `events` object")

    return taxonomy


EVENT_TAXONOMY = _load_event_taxonomy()
EVENT_TAXONOMY_VERSION = EVENT_TAXONOMY.get("version", 1)
ANALYTICS_EVENT_NAMES = tuple(EVENT_TAXONOMY["events"].keys())
DEPRECATED_ANALYTICS_EVENT_ALIASES = MappingProxyType(
    dict(EVENT_TAXONOMY.get("deprecated_aliases", {}))
)


def _to_constant_name(event_name: str) -> str:
    return event_name.upper().replace("-", "_")


ANALYTICS_EVENTS = SimpleNamespace(
    **{
        _to_constant_name(event_name): event_name
        for event_name in ANALYTICS_EVENT_NAMES
    }
)


def normalize_event_name(event_name: str) -> str:
    return DEPRECATED_ANALYTICS_EVENT_ALIASES.get(event_name, event_name)


def is_known_event_name(event_name: str) -> bool:
    return normalize_event_name(event_name) in ANALYTICS_EVENT_NAMES


def get_event_definition(event_name: str) -> dict | None:
    canonical_event_name = normalize_event_name(event_name)
    return EVENT_TAXONOMY["events"].get(canonical_event_name)
