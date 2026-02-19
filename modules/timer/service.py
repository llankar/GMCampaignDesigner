from __future__ import annotations

import time
import uuid
from dataclasses import replace
from typing import Callable, Dict, List, Optional, Protocol, Set

from modules.helpers.logging_helper import log_module_import
from modules.timer.models import TimerPreset, TimerState
from modules.timer.persistence import TimerPersistence

log_module_import(__name__)


class TkAfterScheduler(Protocol):
    def after(self, delay_ms: int, callback: Callable[[], None]) -> str: ...

    def after_cancel(self, after_id: str) -> None: ...


TimerSubscriber = Callable[[List[TimerState]], None]
TimerFinishedSubscriber = Callable[[TimerState], None]


class TimerService:
    def __init__(
        self,
        scheduler: Optional[TkAfterScheduler] = None,
        persistence: Optional[TimerPersistence] = None,
        tick_ms: int = 200,
    ) -> None:
        self._scheduler = scheduler
        self._persistence = persistence or TimerPersistence()
        self._tick_ms = max(50, int(tick_ms))

        self._timers: Dict[str, TimerState] = {}
        self._order: List[str] = []
        self._presets: Dict[str, TimerPreset] = {}
        self._subscribers: Set[TimerSubscriber] = set()
        self._finished_subscribers: Set[TimerFinishedSubscriber] = set()

        self._after_id: Optional[str] = None
        self._last_tick_ts: Optional[float] = None

        self._load_persisted_state()

    def set_scheduler(self, scheduler: TkAfterScheduler) -> None:
        self._scheduler = scheduler
        self._ensure_tick_loop()

    def subscribe(self, callback: TimerSubscriber) -> None:
        self._subscribers.add(callback)
        callback(self.list_timers())

    def unsubscribe(self, callback: TimerSubscriber) -> None:
        self._subscribers.discard(callback)

    def subscribe_finished(self, callback: TimerFinishedSubscriber) -> None:
        self._finished_subscribers.add(callback)

    def unsubscribe_finished(self, callback: TimerFinishedSubscriber) -> None:
        self._finished_subscribers.discard(callback)

    def create_timer(
        self,
        name: str,
        mode: str = "countdown",
        duration: float = 0,
        repeat: bool = False,
        color_tag: str = "",
    ) -> TimerState:
        timer_id = str(uuid.uuid4())
        normalized_mode = "countdown" if mode not in {"countdown", "stopwatch"} else mode
        duration = max(0.0, float(duration or 0.0))
        initial_remaining = duration if normalized_mode == "countdown" else 0.0
        timer = TimerState(
            id=timer_id,
            name=name.strip() or "Timer",
            mode=normalized_mode,
            duration=duration,
            remaining=initial_remaining,
            repeat=bool(repeat),
            color_tag=color_tag,
        )
        self._timers[timer.id] = timer
        self._order.append(timer.id)
        self._persist_and_publish()
        return replace(timer)

    def start(self, timer_id: str) -> Optional[TimerState]:
        timer = self._timers.get(timer_id)
        if timer is None:
            return None

        if timer.mode == "countdown" and timer.remaining <= 0:
            timer.remaining = max(0.0, timer.duration)
        if timer.mode == "stopwatch" and timer.remaining < 0:
            timer.remaining = 0.0

        timer.running = True
        timer.paused = False
        self._last_tick_ts = time.monotonic()
        self._persist_and_publish(schedule=True)
        return replace(timer)

    def pause(self, timer_id: str) -> Optional[TimerState]:
        timer = self._timers.get(timer_id)
        if timer is None:
            return None

        timer.running = False
        timer.paused = True
        self._persist_and_publish()
        return replace(timer)

    def resume(self, timer_id: str) -> Optional[TimerState]:
        timer = self._timers.get(timer_id)
        if timer is None:
            return None

        timer.running = True
        timer.paused = False
        self._last_tick_ts = time.monotonic()
        self._persist_and_publish(schedule=True)
        return replace(timer)

    def stop(self, timer_id: str) -> Optional[TimerState]:
        timer = self._timers.get(timer_id)
        if timer is None:
            return None

        timer.running = False
        timer.paused = False
        self._persist_and_publish()
        return replace(timer)

    def reset(self, timer_id: str) -> Optional[TimerState]:
        timer = self._timers.get(timer_id)
        if timer is None:
            return None

        timer.running = False
        timer.paused = False
        timer.laps.clear()
        timer.remaining = timer.duration if timer.mode == "countdown" else 0.0
        self._persist_and_publish()
        return replace(timer)

    def delete_timer(self, timer_id: str) -> bool:
        if timer_id not in self._timers:
            return False
        self._timers.pop(timer_id, None)
        self._order = [existing_id for existing_id in self._order if existing_id != timer_id]
        self._persist_and_publish()
        return True

    def set_repeat(self, timer_id: str, repeat: bool) -> Optional[TimerState]:
        timer = self._timers.get(timer_id)
        if timer is None:
            return None
        timer.repeat = bool(repeat)
        self._persist_and_publish()
        return replace(timer)

    def add_time(self, timer_id: str, delta_seconds: float) -> Optional[TimerState]:
        timer = self._timers.get(timer_id)
        if timer is None:
            return None

        timer.remaining += float(delta_seconds)
        if timer.mode == "countdown":
            timer.remaining = max(0.0, timer.remaining)
        self._persist_and_publish()
        return replace(timer)

    def subtract_time(self, timer_id: str, delta_seconds: float) -> Optional[TimerState]:
        return self.add_time(timer_id, -float(delta_seconds))

    def lap(self, timer_id: str) -> Optional[float]:
        timer = self._timers.get(timer_id)
        if timer is None:
            return None

        if timer.mode == "countdown":
            value = max(0.0, timer.duration - timer.remaining)
        else:
            value = max(0.0, timer.remaining)
        timer.laps.append(value)
        self._persist_and_publish()
        return value

    def next_in_queue(self) -> Optional[TimerState]:
        for timer_id in self._order:
            timer = self._timers.get(timer_id)
            if timer is None or timer.running:
                continue
            if timer.mode == "countdown" and timer.remaining <= 0 and not timer.repeat:
                continue
            return replace(timer)
        return None

    def list_timers(self) -> List[TimerState]:
        return [replace(self._timers[timer_id]) for timer_id in self._order if timer_id in self._timers]

    def list_presets(self) -> List[TimerPreset]:
        return [replace(preset) for preset in self._presets.values()]

    def save_preset(
        self,
        name: str,
        mode: str,
        duration: float,
        repeat: bool = False,
        color_tag: str = "",
    ) -> TimerPreset:
        preset = TimerPreset(
            id=str(uuid.uuid4()),
            name=name.strip() or "Preset",
            mode=mode if mode in {"countdown", "stopwatch"} else "countdown",
            duration=max(0.0, float(duration or 0.0)),
            repeat=bool(repeat),
            color_tag=color_tag,
        )
        self._presets[preset.id] = preset
        self._persist_and_publish()
        return replace(preset)

    def delete_preset(self, preset_id: str) -> bool:
        if preset_id not in self._presets:
            return False
        self._presets.pop(preset_id, None)
        self._persist_and_publish()
        return True

    def _load_persisted_state(self) -> None:
        timers, presets = self._persistence.load()
        for timer in timers:
            timer.running = False
            timer.paused = False
            self._timers[timer.id] = timer
            self._order.append(timer.id)
        for preset in presets:
            self._presets[preset.id] = preset

    def _tick(self) -> None:
        self._after_id = None
        now = time.monotonic()
        delta = max(0.0, now - (self._last_tick_ts or now))
        self._last_tick_ts = now

        changed = False
        for timer in self._timers.values():
            if not timer.running:
                continue

            if timer.mode == "countdown":
                timer.remaining = max(0.0, timer.remaining - delta)
                if timer.remaining <= 0:
                    if timer.repeat and timer.duration > 0:
                        timer.remaining = timer.duration
                    else:
                        timer.running = False
                        timer.paused = False
                        self._notify_finished(timer)
                changed = True
            else:
                timer.remaining += delta
                if timer.duration > 0 and timer.remaining >= timer.duration:
                    if timer.repeat:
                        timer.remaining = 0.0
                    else:
                        timer.remaining = timer.duration
                        timer.running = False
                        timer.paused = False
                        self._notify_finished(timer)
                changed = True

        if changed:
            self._persist()
            self._notify_subscribers()

        self._ensure_tick_loop()

    def _ensure_tick_loop(self) -> None:
        if self._scheduler is None:
            return
        if self._after_id is not None:
            return
        if not any(timer.running for timer in self._timers.values()):
            self._last_tick_ts = None
            return
        self._after_id = self._scheduler.after(self._tick_ms, self._tick)

    def _notify_subscribers(self) -> None:
        snapshot = self.list_timers()
        for callback in list(self._subscribers):
            callback(snapshot)

    def _persist(self) -> None:
        self._persistence.save(self.list_timers(), self.list_presets())

    def _persist_and_publish(self, schedule: bool = False) -> None:
        self._persist()
        self._notify_subscribers()
        if schedule:
            self._ensure_tick_loop()
        elif self._after_id and not any(timer.running for timer in self._timers.values()):
            assert self._scheduler is not None
            self._scheduler.after_cancel(self._after_id)
            self._after_id = None

    def _notify_finished(self, timer: TimerState) -> None:
        snapshot = replace(timer)
        for callback in list(self._finished_subscribers):
            callback(snapshot)
