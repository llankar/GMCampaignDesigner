"""Helper that launches pywebview in a separate process."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from modules.helpers.logging_helper import log_exception, log_module_import

log_module_import(__name__)


@dataclass(slots=True)
class PyWebviewClient:
    title: str = "Image Browser"
    width: int = 1100
    height: int = 760
    min_width: int = 900
    min_height: int = 620

    def open(self, url: str) -> None:
        args = [
            sys.executable,
            "-m",
            "modules.ui.webview.pywebview_launcher",
            url,
            "--title",
            self.title,
            "--width",
            str(self.width),
            "--height",
            str(self.height),
            "--min-width",
            str(self.min_width),
            "--min-height",
            str(self.min_height),
        ]
        try:
            subprocess.Popen(args)
        except Exception as exc:  # pragma: no cover - UI fallback
            log_exception(
                f"Unable to launch pywebview for {url}: {exc}",
                func_name="PyWebviewClient.open",
            )
            raise
