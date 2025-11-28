import json
import os
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import, log_info

log_module_import(__name__)

DEFAULT_SIZE: Tuple[int, int] = (1920, 1080)


def _storage_path() -> str:
    campaign_dir = ConfigHelper.get_campaign_dir()
    os.makedirs(campaign_dir, exist_ok=True)
    return os.path.join(campaign_dir, "whiteboard_state.json")


@dataclass
class WhiteboardState:
    items: List[Dict[str, Any]] = field(default_factory=list)
    size: Tuple[int, int] = field(default_factory=lambda: DEFAULT_SIZE)

    @staticmethod
    def from_dict(raw: Dict[str, Any]) -> "WhiteboardState":
        items = raw.get("items") or []
        size = tuple(raw.get("size") or DEFAULT_SIZE)
        try:
            if len(size) != 2:
                size = DEFAULT_SIZE
        except Exception:
            size = DEFAULT_SIZE
        return WhiteboardState(items=list(items), size=size)  # shallow copy to avoid mutation leaks

    def to_dict(self) -> Dict[str, Any]:
        serialized_items = []
        for item in self.items:
            clean = {k: v for k, v in item.items() if k not in ("canvas_ids",)}
            serialized_items.append(clean)
        return {"items": serialized_items, "size": list(self.size)}


class WhiteboardStorage:
    """Manage persistence of whiteboard strokes/text independent of maps."""

    @staticmethod
    def load_state() -> WhiteboardState:
        path = _storage_path()
        if not os.path.exists(path):
            return WhiteboardState()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return WhiteboardState.from_dict(data)
        except Exception:
            return WhiteboardState()

    @staticmethod
    def save_state(state: WhiteboardState) -> None:
        path = _storage_path()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(state.to_dict(), fh, ensure_ascii=False, indent=2)
            log_info("Saved whiteboard state", func_name="WhiteboardStorage.save_state")
        except Exception:
            # Failing to persist should not break drawing; swallow quietly
            pass

    @staticmethod
    def clear_state() -> None:
        path = _storage_path()
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
