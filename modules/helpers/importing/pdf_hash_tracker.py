from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_exception, log_module_import

log_module_import(__name__)


class PDFHashTracker:
    """Track imported PDF hashes to avoid repeated imports."""

    HISTORY_FILENAME = "imported_pdfs.json"

    @classmethod
    def _history_path(cls) -> Path:
        campaign_dir = ConfigHelper.get_campaign_dir()
        return Path(campaign_dir) / cls.HISTORY_FILENAME

    @classmethod
    def compute_hash(cls, pdf_path: str) -> str:
        sha256 = hashlib.sha256()
        path = Path(pdf_path)
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @classmethod
    def _load_history(cls) -> Dict[str, Dict[str, str]]:
        path = cls._history_path()
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data.get("hashes", {}) if isinstance(data, dict) else {}
        except Exception as exc:
            log_exception(
                f"Unable to read PDF import history: {exc}",
                func_name="PDFHashTracker._load_history",
            )
            return {}

    @classmethod
    def _save_history(cls, hashes: Dict[str, Dict[str, str]]):
        path = cls._history_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"hashes": hashes}, handle, indent=2)
        except Exception as exc:
            log_exception(
                f"Unable to store PDF import history: {exc}",
                func_name="PDFHashTracker._save_history",
            )

    @classmethod
    def get_record(cls, pdf_hash: str) -> Optional[Dict[str, str]]:
        hashes = cls._load_history()
        return hashes.get(pdf_hash)

    @classmethod
    def is_already_imported(cls, pdf_hash: str) -> bool:
        return cls.get_record(pdf_hash) is not None

    @classmethod
    def record_import(cls, pdf_hash: str, source_path: str):
        hashes = cls._load_history()
        hashes[pdf_hash] = {
            "path": str(source_path),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        cls._save_history(hashes)
