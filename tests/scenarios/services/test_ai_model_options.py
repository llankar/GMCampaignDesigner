"""Tests for AI model selector option preparation."""

from modules.scenarios.services.ai_model_options import build_ai_model_options


def test_build_ai_model_options_preserves_discovered_models():
    """Verify discovered Ollama models are added alongside the fallback model."""
    options, selected = build_ai_model_options(
        configured_model="llama3.1",
        last_used_model="gpt-oss:20b",
        discovered_models=["qwen2.5:7b", "phi4:latest"],
        current_model="gpt-oss:20b",
    )

    assert options == ["gpt-oss:20b", "qwen2.5:7b", "phi4:latest", "llama3.1"]
    assert selected == "gpt-oss:20b"


def test_build_ai_model_options_keeps_fallback_when_discovery_empty():
    """Verify the selector never becomes empty when discovery returns no models."""
    options, selected = build_ai_model_options(
        configured_model="llama3.1",
        last_used_model=None,
        discovered_models=[],
    )

    assert options == ["llama3.1"]
    assert selected == "llama3.1"
