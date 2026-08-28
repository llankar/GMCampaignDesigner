"""Readable errors for GitHub Releases API failures."""

from __future__ import annotations

from typing import Any


def describe_github_error(response: Any) -> str:
    """Return GitHub's useful validation details without exposing credentials."""
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return str(getattr(response, "text", "") or "").strip()

    if not isinstance(payload, dict):
        return ""
    details = [str(payload.get("message") or "").strip()]
    errors = payload.get("errors")
    if isinstance(errors, list):
        for error in errors:
            if isinstance(error, dict):
                parts = [error.get("resource"), error.get("field"), error.get("code")]
                detail = " ".join(str(part) for part in parts if part)
            else:
                detail = str(error)
            if detail:
                details.append(detail)
    return ": ".join(detail for detail in details if detail)


def raise_for_github_status(response: Any, *, action: str) -> None:
    """Raise an actionable error containing GitHub's validation response."""
    try:
        response.raise_for_status()
    except Exception as exc:
        detail = describe_github_error(response)
        if detail:
            raise RuntimeError(f"{action}: {detail}") from exc
        raise
