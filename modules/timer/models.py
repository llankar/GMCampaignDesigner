from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class TimerState:
    id: str
    name: str
    mode: str = "countdown"
    duration: float = 0.0
    remaining: float = 0.0
    running: bool = False
    paused: bool = False
    repeat: bool = False
    laps: List[float] = field(default_factory=list)
    color_tag: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimerState":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "Timer")),
            mode=str(data.get("mode", "countdown")),
            duration=float(data.get("duration", 0.0) or 0.0),
            remaining=float(data.get("remaining", 0.0) or 0.0),
            running=bool(data.get("running", False)),
            paused=bool(data.get("paused", False)),
            repeat=bool(data.get("repeat", False)),
            laps=[float(value) for value in (data.get("laps") or [])],
            color_tag=str(data.get("color_tag", "")),
            created_at=str(data.get("created_at", datetime.now(timezone.utc).isoformat())),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "mode": self.mode,
            "duration": float(self.duration),
            "remaining": float(self.remaining),
            "running": self.running,
            "paused": self.paused,
            "repeat": self.repeat,
            "laps": [float(value) for value in self.laps],
            "color_tag": self.color_tag,
            "created_at": self.created_at,
        }


@dataclass
class TimerPreset:
    id: str
    name: str
    mode: str = "countdown"
    duration: float = 0.0
    repeat: bool = False
    color_tag: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimerPreset":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "Preset")),
            mode=str(data.get("mode", "countdown")),
            duration=float(data.get("duration", 0.0) or 0.0),
            repeat=bool(data.get("repeat", False)),
            color_tag=str(data.get("color_tag", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "mode": self.mode,
            "duration": float(self.duration),
            "repeat": self.repeat,
            "color_tag": self.color_tag,
        }
