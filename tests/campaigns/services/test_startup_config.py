"""Regression tests for startup config."""

from __future__ import annotations

from modules.campaigns.services.startup_config import DEFAULT_MODELS_PATH, load_startup_model_config


def test_load_startup_model_config_uses_configured_path_and_models() -> None:
    """Verify that load startup model config uses configured path and models."""
    config = load_startup_model_config(
        config_getter=lambda *_args, **_kwargs: "X:/models",
        model_loader=lambda: ("sdxl", "flux"),
    )

    assert config.models_path == "X:/models"
    assert config.model_options == ["sdxl", "flux"]


def test_load_startup_model_config_falls_back_to_default_path() -> None:
    """Verify that load startup model config falls back to default path."""
    config = load_startup_model_config(
        config_getter=lambda *_args, **_kwargs: None,
        model_loader=lambda: (),
    )

    assert config.models_path == DEFAULT_MODELS_PATH
    assert config.model_options == []
