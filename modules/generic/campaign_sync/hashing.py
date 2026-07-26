"""Deterministic SHA-256 hashing for campaign snapshots."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_campaign_snapshot(campaign_root: Path) -> str:
    """Compatibility wrapper for the canonical synchronized-content hash."""
    from .change_detector import calculate_campaign_fingerprint

    return calculate_campaign_fingerprint(campaign_root)
