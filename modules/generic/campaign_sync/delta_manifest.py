"""Versioned, content-addressed manifests for campaign delta bundles."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

DELTA_FORMAT_VERSION = 1


def normalize_sync_path(value: str) -> str:
    text = str(value).replace("\\", "/")
    path = Path(text)
    if (
        not text
        or path.is_absolute()
        or path.drive
        or text.startswith("//")
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise ValueError(f"invalid synchronized-content path: {value!r}")
    return path.as_posix()


@dataclass(frozen=True)
class InventoryEntry:
    path: str
    sha256: str
    size: int
    file_type: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", normalize_sync_path(self.path))
        digest = self.sha256.lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid inventory SHA-256")
        object.__setattr__(self, "sha256", digest)
        if self.size < 0 or self.file_type not in {"database", "asset", "extra_file"}:
            raise ValueError("invalid inventory entry")

    @classmethod
    def from_dict(cls, value: dict) -> "InventoryEntry":
        return cls(str(value["path"]), str(value["sha256"]), int(value["size"]), str(value["file_type"]))


@dataclass(frozen=True)
class DeltaManifest:
    base_revision: int
    base_content_fingerprint: str
    files: tuple[InventoryEntry, ...]
    tombstones: tuple[str, ...]
    inventory: tuple[InventoryEntry, ...]
    version: int = DELTA_FORMAT_VERSION

    def __post_init__(self) -> None:
        if self.version != DELTA_FORMAT_VERSION or self.base_revision < 1:
            raise ValueError("unsupported delta manifest")
        fingerprint = self.base_content_fingerprint.lower()
        if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
            raise ValueError("invalid base fingerprint")
        object.__setattr__(self, "base_content_fingerprint", fingerprint)
        files = inventory_map(self.files)
        inventory = inventory_map(self.inventory)
        object.__setattr__(self, "tombstones", tuple(normalize_sync_path(p) for p in self.tombstones))
        if len(set(self.tombstones)) != len(self.tombstones):
            raise ValueError("duplicate tombstone path")
        if set(files) & set(self.tombstones):
            raise ValueError("a delta path cannot be both changed and deleted")
        if any(inventory.get(path) != entry for path, entry in files.items()):
            raise ValueError("delta payload is inconsistent with its resulting inventory")

    def to_dict(self) -> dict:
        return {"version": self.version, "base_revision": self.base_revision,
                "base_content_fingerprint": self.base_content_fingerprint,
                "files": [asdict(x) for x in self.files], "tombstones": list(self.tombstones),
                "inventory": [asdict(x) for x in self.inventory]}

    @classmethod
    def from_dict(cls, value: dict) -> "DeltaManifest":
        return cls(int(value["base_revision"]), str(value["base_content_fingerprint"]),
                   tuple(InventoryEntry.from_dict(x) for x in value.get("files", ())),
                   tuple(str(x) for x in value.get("tombstones", ())),
                   tuple(InventoryEntry.from_dict(x) for x in value.get("inventory", ())),
                   int(value.get("version", 0)))


def inventory_map(entries: Iterable[InventoryEntry]) -> dict[str, InventoryEntry]:
    values = tuple(entries)
    result = {entry.path: entry for entry in values}
    if len(result) != len(values):
        raise ValueError("duplicate inventory path")
    return result
