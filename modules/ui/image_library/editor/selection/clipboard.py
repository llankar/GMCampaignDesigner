"""In-app clipboard payload for selection cut/copy/paste."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass
class SelectionClipboardPayload:
    """Image payload and destination offset."""

    image: Image.Image
    offset: tuple[int, int]


class SelectionClipboard:
    """Simple in-memory clipboard reserved for editor selections."""

    def __init__(self) -> None:
        self._payload: SelectionClipboardPayload | None = None

    def set(self, image: Image.Image, offset: tuple[int, int]) -> None:
        self._payload = SelectionClipboardPayload(image=image.convert("RGBA"), offset=(int(offset[0]), int(offset[1])))

    def get(self) -> SelectionClipboardPayload | None:
        if self._payload is None:
            return None
        return SelectionClipboardPayload(image=self._payload.image.copy(), offset=self._payload.offset)

    def has_data(self) -> bool:
        return self._payload is not None

    def clear(self) -> None:
        self._payload = None
