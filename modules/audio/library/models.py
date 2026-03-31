"""Data models for library."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class Track:
    id: str
    name: str
    path: str
    category: str
    mood: str

    def to_dict(self) -> Dict[str, str]:
        """Handle to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "category": self.category,
            "mood": self.mood,
        }


@dataclass(slots=True)
class MoodBucket:
    name: str
    tracks: List[Track] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Handle to dict."""
        return {
            "tracks": [track.to_dict() for track in self.tracks],
        }


@dataclass(slots=True)
class Category:
    name: str
    directories: List[str] = field(default_factory=list)
    moods: Dict[str, MoodBucket] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Handle to dict."""
        return {
            "directories": list(self.directories),
            "moods": {mood: bucket.to_dict() for mood, bucket in self.moods.items()},
        }
