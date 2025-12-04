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
    grid_enabled: bool = False
    grid_size: int = 50
    snap_to_grid: bool = False
    active_layer: str = "shared"
    show_shared_layer: bool = True
    show_gm_layer: bool = True
    zoom: float = 1.0
    remote_edit_enabled: bool = False

    @staticmethod
    def from_dict(raw: Dict[str, Any]) -> "WhiteboardState":
        items = raw.get("items") or []
        size = tuple(raw.get("size") or DEFAULT_SIZE)
        try:
            if len(size) != 2:
                size = DEFAULT_SIZE
        except Exception:
            size = DEFAULT_SIZE
        return WhiteboardState(
            items=list(items),
            size=size,
            grid_enabled=bool(raw.get("grid_enabled", False)),
            grid_size=int(raw.get("grid_size", 50) or 50),
            snap_to_grid=bool(raw.get("snap_to_grid", False)),
            active_layer=str(raw.get("active_layer", "shared")),
            show_shared_layer=bool(raw.get("show_shared_layer", True)),
            show_gm_layer=bool(raw.get("show_gm_layer", True)),
            zoom=float(raw.get("zoom", 1.0) or 1.0),
            remote_edit_enabled=bool(raw.get("remote_edit_enabled", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        serialized_items = []
        for item in self.items:
            clean = {
                k: v
                for k, v in item.items()
                if k not in ("canvas_ids", "_image_ref", "asset_path")
            }
            serialized_items.append(clean)
        return {
            "items": serialized_items,
            "size": list(self.size),
            "grid_enabled": self.grid_enabled,
            "grid_size": int(self.grid_size),
            "snap_to_grid": self.snap_to_grid,
            "active_layer": self.active_layer,
            "show_shared_layer": self.show_shared_layer,
            "show_gm_layer": self.show_gm_layer,
            "zoom": float(self.zoom),
            "remote_edit_enabled": self.remote_edit_enabled,
        }


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
