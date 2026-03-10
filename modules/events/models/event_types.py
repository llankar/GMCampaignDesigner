from dataclasses import dataclass


@dataclass(frozen=True)
class EventType:
    key: str
    label: str
    color: str


EVENT_TYPES = {
    "session": EventType("session", "Session", "#4F8EF7"),
    "intrigue": EventType("intrigue", "Intrigue", "#C96CFF"),
    "villain": EventType("villain", "Villain", "#A63DE0"),
    "pnj": EventType("pnj", "PNJ", "#FF9F43"),
    "lore": EventType("lore", "Lore", "#5AC8A8"),
}

DEFAULT_EVENT_TYPE = EventType("autre", "Autre", "#7A7A7A")


def normalize_event_type_key(value):
    text = str(value or "").strip().lower()
    return text if text in EVENT_TYPES else DEFAULT_EVENT_TYPE.key


def get_event_type(value):
    key = normalize_event_type_key(value)
    return EVENT_TYPES.get(key, DEFAULT_EVENT_TYPE)


def event_type_labels():
    return [item.label for item in EVENT_TYPES.values()]
