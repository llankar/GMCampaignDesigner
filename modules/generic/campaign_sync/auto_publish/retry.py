"""Failure classification and bounded exponential retry policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.error import HTTPError, URLError

from modules.generic.campaign_sync.publisher import StaleParentError


class FailureCategory(str, Enum):
    TRANSIENT = "transient"
    RATE_LIMIT = "rate_limit"
    OFFLINE = "offline"
    CREDENTIALS = "credentials"
    AUTHENTICATION = "authentication"
    CONFIGURATION = "configuration"
    CONFLICT = "conflict"
    PERMANENT = "permanent"


def classify_failure(error: BaseException) -> FailureCategory:
    if isinstance(error, StaleParentError):
        return FailureCategory.CONFLICT
    if isinstance(error, HTTPError):
        if error.code in (401, 403):
            return FailureCategory.AUTHENTICATION
        if error.code == 429:
            return FailureCategory.RATE_LIMIT
        if error.code >= 500:
            return FailureCategory.TRANSIENT
        return FailureCategory.CONFIGURATION
    if isinstance(error, (URLError, ConnectionError, TimeoutError, OSError)):
        return FailureCategory.TRANSIENT
    text = str(error).lower()
    if "token" in text or "credential" in text:
        return FailureCategory.CREDENTIALS
    if "config" in text or "repository" in text:
        return FailureCategory.CONFIGURATION
    return FailureCategory.PERMANENT


@dataclass(frozen=True)
class RetryPolicy:
    initial_delay: float = 5.0
    maximum_delay: float = 900.0
    maximum_attempts: int = 8

    def delay(self, retry_count: int) -> float:
        return min(self.maximum_delay, self.initial_delay * (2 ** max(0, retry_count)))

    def should_retry(self, category: FailureCategory, retry_count: int) -> bool:
        return category in (FailureCategory.TRANSIENT, FailureCategory.RATE_LIMIT) and retry_count < self.maximum_attempts
