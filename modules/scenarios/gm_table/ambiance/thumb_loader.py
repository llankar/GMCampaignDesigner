"""Lazy thumbnail scheduling with cache and stale-job protection."""

from __future__ import annotations

from collections import OrderedDict

import customtkinter as ctk


class AmbianceThumbLoader:
    """Load thumbnails lazily for currently visible cards only."""

    def __init__(self, host: ctk.CTkBaseClass, *, thumbnailer, cache_size: int = 180) -> None:
        self._host = host
        self._thumbnailer = thumbnailer
        self._cache_size = max(32, int(cache_size))
        self._cache: OrderedDict[str, ctk.CTkImage] = OrderedDict()
        self._active_card_jobs: dict[str, tuple[int, str]] = {}
        self._next_token = 1

    def request(
        self,
        *,
        card_key: str,
        thumb_key: str,
        absolute_path: str,
        media_type: str,
        on_ready,
    ) -> None:
        cached = self._cache.get(thumb_key)
        if cached is not None:
            self._cache.move_to_end(thumb_key)
            on_ready(cached)
            return

        token = self._next_token
        self._next_token += 1
        self._active_card_jobs[card_key] = (token, thumb_key)

        def _load_later() -> None:
            current = self._active_card_jobs.get(card_key)
            if current != (token, thumb_key):
                return
            image = self._thumbnailer.get(absolute_path, media_type=media_type)
            self._cache[thumb_key] = image
            self._cache.move_to_end(thumb_key)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
            current = self._active_card_jobs.get(card_key)
            if current == (token, thumb_key):
                on_ready(image)

        self._host.after(0, _load_later)

    def invalidate_card(self, card_key: str) -> None:
        self._active_card_jobs.pop(card_key, None)

    def clear(self) -> None:
        self._cache.clear()
        self._active_card_jobs.clear()
