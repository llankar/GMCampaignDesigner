"""Tests for Ollama model discovery."""

from modules.ai.ollama_model_service import OllamaModelService


def test_list_models_from_cli_parses_ollama_table(monkeypatch):
    """Verify that ``ollama list`` output is parsed into model names."""

    class Completed:
        stdout = (
            "NAME                    ID              SIZE      MODIFIED\n"
            "llama3.1:8b              abc123          4.9 GB    2 days ago\n"
            "mistral:latest           def456          4.1 GB    1 week ago\n"
        )

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Completed()

    monkeypatch.setattr("modules.ai.ollama_model_service.subprocess.run", fake_run)

    assert OllamaModelService._list_models_from_cli() == ["llama3.1:8b", "mistral:latest"]
    command, kwargs = calls[0]
    assert command == ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "ollama list"]
    assert kwargs == {
        "capture_output": True,
        "check": True,
        "text": True,
        "timeout": 10,
    }


def test_list_models_falls_back_to_tags_api(monkeypatch):
    """Verify that model discovery falls back to Ollama's tags endpoint."""

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "qwen2.5:7b"}, {"name": "phi4:latest"}]}

    monkeypatch.setattr(OllamaModelService, "_list_models_from_cli", staticmethod(lambda: []))
    monkeypatch.setattr("modules.ai.ollama_model_service.requests.get", lambda *args, **kwargs: Response())

    assert OllamaModelService("http://localhost:11434").list_models() == ["qwen2.5:7b", "phi4:latest"]
