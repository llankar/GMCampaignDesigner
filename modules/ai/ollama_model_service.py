"""Helpers for discovering locally available Ollama models."""

from __future__ import annotations

import subprocess
from typing import Any

import requests


class OllamaModelService:
    """Discover model names from Ollama without requiring generation calls."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        """Initialize the OllamaModelService instance."""
        self.base_url = (base_url or "http://127.0.0.1:11434").rstrip("/")

    def list_models(self) -> list[str]:
        """Return available Ollama model names, preferring ``ollama list`` output."""
        models = self._list_models_from_cli()
        if models:
            return models
        return self._list_models_from_api()

    @staticmethod
    def _list_models_from_cli() -> list[str]:
        """Return model names from the ``ollama list`` command."""
        commands = (
            ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "ollama list"],
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "ollama list"],
            ["ollama", "list"],
        )

        for command in commands:
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    check=True,
                    text=True,
                    timeout=10,
                )
            except Exception:
                continue

            names: list[str] = []
            for line in (completed.stdout or "").splitlines():
                line = line.strip()
                if not line or line.lower().startswith("name"):
                    continue
                name = line.split()[0].strip()
                if name and name not in names:
                    names.append(name)
            return names

        return []

    def _list_models_from_api(self) -> list[str]:
        """Return model names from Ollama's HTTP tags endpoint."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            payload: Any = response.json()
        except Exception:
            return []

        names: list[str] = []
        for model in payload.get("models", []) if isinstance(payload, dict) else []:
            if not isinstance(model, dict):
                continue
            name = str(model.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
        return names
