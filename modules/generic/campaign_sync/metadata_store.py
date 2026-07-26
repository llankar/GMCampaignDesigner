"""Atomic persistence for shared and installation-local sync state."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from uuid import uuid4

from .models import CampaignSyncMetadata

SYNC_RELATIVE_PATH = Path(".gmcd") / "sync.json"


def _atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


@dataclass
class CampaignSyncMetadataStore:
    campaign_root: Path

    @property
    def path(self) -> Path:
        return Path(self.campaign_root) / SYNC_RELATIVE_PATH

    def read(self) -> Optional[CampaignSyncMetadata]:
        if not self.path.exists():
            return None
        value = json.loads(self.path.read_text(encoding="utf-8"))
        return CampaignSyncMetadata.from_dict(value)

    def write(self, metadata: CampaignSyncMetadata) -> None:
        _atomic_json_write(self.path, metadata.to_dict())


class InstallationStateStore:
    """Machine-local state, deliberately stored outside every campaign."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path or (Path.home() / ".gmcd" / "installation.json"))

    def read(self) -> dict:
        if not self.path.exists():
            return {}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}

    def write(self, state: dict) -> None:
        _atomic_json_write(self.path, state)

    def installation_id(self) -> str:
        state = self.read()
        value = state.get("installation_id")
        if value:
            return str(value)
        value = str(uuid4())
        state["installation_id"] = value
        self.write(state)
        return value
