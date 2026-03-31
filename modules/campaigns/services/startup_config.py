"""Utilities for campaign startup config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.swarmui_helper import get_available_models


DEFAULT_MODELS_PATH = r"E:\SwarmUI\SwarmUI\Models\Stable-diffusion"


@dataclass(frozen=True)
class StartupModelConfig:
    models_path: str
    model_options: list[str]


def load_startup_model_config(
    *,
    config_getter: Callable[..., str | None] | None = None,
    model_loader: Callable[[], Sequence[str]] | None = None,
    default_models_path: str = DEFAULT_MODELS_PATH,
) -> StartupModelConfig:
    """Load non-UI startup configuration used by MainWindow."""

    config_getter = config_getter or ConfigHelper.get
    model_loader = model_loader or get_available_models

    models_path = config_getter("Paths", "models_path", fallback=default_models_path) or default_models_path
    model_options = list(model_loader())
    return StartupModelConfig(models_path=models_path, model_options=model_options)
