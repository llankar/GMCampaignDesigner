"""Centralized, bounded token animation lifecycle for Tk canvases."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import queue
import time

from .decoder import MediaDecodeError, VideoDecoder


class TokenAnimationManager:
    """Decode outside Tk and deliver frames from one centralized ``after`` loop."""

    def __init__(self, widget, on_frame, *, fps: int = 12, max_size: int = 256, workers: int = 2):
        self.widget = widget
        self.on_frame = on_frame
        self.fps = min(15, max(1, int(fps)))
        self.max_size = min(512, max(32, int(max_size)))
        self._executor = ThreadPoolExecutor(max_workers=max(1, min(4, workers)), thread_name_prefix="map-media")
        self._entries = {}
        self._results = queue.SimpleQueue()
        self._after_id = None
        self._closed = False

    def register(self, token: dict, path: str) -> bool:
        if self._closed:
            return False
        self.unregister(token)
        try:
            decoder = VideoDecoder(path, max_size=self.max_size)
        except MediaDecodeError:
            return False
        key = id(token)
        self._entries[key] = {"token": token, "decoder": decoder, "busy": False, "due": 0.0}
        self._ensure_tick()
        return True

    def unregister(self, token: dict) -> None:
        entry = self._entries.pop(id(token), None)
        if entry:
            # ``close`` may wait for an in-flight PyAV decode.  Never make Tk's
            # event thread wait for that lock.
            self._executor.submit(entry["decoder"].close)

    def clear(self) -> None:
        for entry in list(self._entries.values()):
            self._executor.submit(entry["decoder"].close)
        self._entries.clear()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.clear()
        # Keep queued decoder closes: cancelling them would leak containers.
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _ensure_tick(self) -> None:
        if not self._closed and self._after_id is None:
            self._after_id = self.widget.after(15, self._tick)

    def _decode(self, key, decoder) -> None:
        try:
            self._results.put((key, decoder.read_frame(), None))
        except Exception as exc:
            self._results.put((key, None, exc))

    def _tick(self) -> None:
        self._after_id = None
        if self._closed:
            return
        while True:
            try:
                key, frame, error = self._results.get_nowait()
            except queue.Empty:
                break
            entry = self._entries.get(key)
            if not entry:
                continue
            entry["busy"] = False
            entry["due"] = time.monotonic() + 1.0 / self.fps
            if error is not None:
                self.unregister(entry["token"])
            elif frame is not None:
                try:
                    self.on_frame(entry["token"], frame)
                except Exception:
                    self.unregister(entry["token"])
        now = time.monotonic()
        for key, entry in list(self._entries.items()):
            if not entry["busy"] and now >= entry["due"]:
                entry["busy"] = True
                self._executor.submit(self._decode, key, entry["decoder"])
        if self._entries:
            self._ensure_tick()
