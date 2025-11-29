import os
from functools import lru_cache
from typing import List, Tuple

from PIL import Image, ImageTk

ASSET_ROOTS = [
    os.path.join("assets", "icons"),
    os.path.join("assets"),
]


def _is_image_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in {".png", ".jpg", ".jpeg"}


def available_stamp_assets() -> List[str]:
    discovered: List[str] = []
    for root in ASSET_ROOTS:
        if not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            candidate = os.path.join(root, name)
            if os.path.isfile(candidate) and _is_image_file(candidate):
                discovered.append(candidate)
    discovered.sort()
    return discovered


@lru_cache(maxsize=64)
def load_pil_asset(path: str, size: int) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    size_px = max(8, int(size))
    return img.resize((size_px, size_px), Image.LANCZOS)


@lru_cache(maxsize=64)
def load_tk_asset(path: str, size: int) -> ImageTk.PhotoImage:
    pil_img = load_pil_asset(path, size)
    return ImageTk.PhotoImage(pil_img)


def reset_cache():
    load_pil_asset.cache_clear()
    load_tk_asset.cache_clear()

