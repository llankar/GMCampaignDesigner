"""Canonical, campaign-relative paths for image-library assets.

Persisted references always use POSIX separators.  Absolute paths are accepted
only as a temporary read-compatibility measure and are converted before writes.
"""

from __future__ import annotations

import ntpath
from pathlib import Path, PurePosixPath

from modules.helpers.config_helper import ConfigHelper


class InvalidAssetReference(ValueError):
    """Raised when an asset reference could escape the active campaign."""


def _campaign_root(campaign_dir: str | Path | None = None) -> Path:
    return Path(campaign_dir or ConfigHelper.get_campaign_dir()).expanduser().resolve()


def _looks_windows_absolute(value: str) -> bool:
    return ntpath.isabs(value) or (len(value) > 2 and value[1] == ":" and value[2] in "\\/")


def normalize_asset_reference(reference: str | Path, campaign_dir: str | Path | None = None) -> str:
    """Return a safe canonical reference, converting legacy absolute values.

    Legacy absolute references must either be below the active campaign or have
    a recognisable ``assets/image_library`` suffix (for a moved campaign).
    """
    raw = str(reference or "").strip()
    if not raw:
        return ""
    root = _campaign_root(campaign_dir)
    windows_absolute = _looks_windows_absolute(raw)
    candidate = Path(raw).expanduser()
    normalized = raw.replace("\\", "/")
    if candidate.is_absolute() or windows_absolute:
        # A Windows value can be made relative normally when running on Windows.
        if candidate.is_absolute():
            try:
                return make_campaign_relative(candidate, root)
            except InvalidAssetReference:
                # A campaign may have moved since this value was persisted.
                # Only remap the managed image-library suffix; arbitrary
                # absolute paths remain invalid.
                pass
        marker = "/assets/image_library/"
        lowered = normalized.lower()
        index = lowered.find(marker)
        if index >= 0:
            normalized = normalized[index + 1 :]
        else:
            raise InvalidAssetReference(f"absolute asset is outside campaign: {raw}")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    parts = PurePosixPath(normalized).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise InvalidAssetReference(f"invalid asset reference: {raw}")
    return PurePosixPath(*parts).as_posix()


def make_campaign_relative(path: str | Path, campaign_dir: str | Path | None = None) -> str:
    """Convert an existing filesystem path below the campaign to a reference."""
    root = _campaign_root(campaign_dir)
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        return normalize_asset_reference(candidate, root)
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise InvalidAssetReference(f"asset is outside campaign: {path}") from exc
    return normalize_asset_reference(relative, root)


def resolve_asset_reference(reference: str | Path, campaign_dir: str | Path | None = None) -> Path:
    """Resolve a persisted reference safely against the active campaign root."""
    root = _campaign_root(campaign_dir)
    canonical = normalize_asset_reference(reference, root)
    if not canonical:
        raise InvalidAssetReference("empty asset reference")
    resolved = (root / Path(*PurePosixPath(canonical).parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise InvalidAssetReference(f"asset resolves outside campaign: {reference}") from exc
    return resolved
