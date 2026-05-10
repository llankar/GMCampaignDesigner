"""Optional access to :mod:`tkhtmlview` without hard dependency failures.

Some screens can render richer descriptions with ``tkhtmlview`` when the
package is installed.  The application must still start when that optional
package is missing, so this module probes for it before loading it and exposes
``None`` when unavailable.
"""

from __future__ import annotations

from importlib import import_module, util
from typing import Any


_TKHTMLVIEW_SPEC = util.find_spec("tkhtmlview")
HTMLLabel: type[Any] | None = (
    getattr(import_module("tkhtmlview"), "HTMLLabel") if _TKHTMLVIEW_SPEC is not None else None
)


def is_html_label_available() -> bool:
    """Return whether the optional rich HTML label widget can be used."""

    return HTMLLabel is not None
