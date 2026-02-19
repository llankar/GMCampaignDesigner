from __future__ import annotations

from typing import Optional

from modules.timer.service import TimerService, TkAfterScheduler

_timer_service: Optional[TimerService] = None


def get_timer_service(scheduler: Optional[TkAfterScheduler] = None) -> TimerService:
    global _timer_service
    if _timer_service is None:
        _timer_service = TimerService(scheduler=scheduler)
    elif scheduler is not None:
        _timer_service.set_scheduler(scheduler)
    return _timer_service


__all__ = ["TimerService", "get_timer_service"]
