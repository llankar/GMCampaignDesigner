from enum import Enum


class WhiteboardLayer(str, Enum):
    SHARED = "shared"
    GM = "gm"


def normalize_layer(value: str | None) -> str:
    try:
        candidate = str(value or "").lower().strip()
    except Exception:
        candidate = ""
    return WhiteboardLayer.GM.value if candidate == WhiteboardLayer.GM.value else WhiteboardLayer.SHARED.value

