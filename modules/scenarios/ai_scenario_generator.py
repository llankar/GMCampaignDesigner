"""AI scenario generation service and text parsing helpers."""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Mapping

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_exception
from modules.scenarios.ai_prompt_library import ScenarioPrompt, extract_placeholders
from modules.scenarios.generated_scenario_parser import normalize_generated_scenario_payload


class AIGenerationError(RuntimeError):
    """Raised when AI scenario generation fails."""


@dataclass
class AIProviderConfig:
    """Configuration for an AI chat provider."""

    base_url: str = "http://localhost:11434"
    model: str = "llama3.1"
    temperature: float = 0.7
    timeout: int = 120

    @classmethod
    def from_config(cls) -> "AIProviderConfig":
        """Load provider configuration from ConfigHelper."""
        return cls(
            base_url=(ConfigHelper.get("AI", "base_url", fallback="http://localhost:11434") or "http://localhost:11434").rstrip("/"),
            model=ConfigHelper.get("AI", "model", fallback="llama3.1") or "llama3.1",
            temperature=float(ConfigHelper.get("AI", "temperature", fallback="0.7") or 0.7),
            timeout=int(float(ConfigHelper.get("AI", "timeout", fallback="120") or 120)),
        )


class OllamaScenarioProvider:
    """Minimal Ollama /api/chat provider."""

    def __init__(self, config: AIProviderConfig | None = None):
        self.config = config or AIProviderConfig.from_config()

    def generate(self, prompt: str) -> str:
        """Send prompt to Ollama and return generated text."""
        url = f"{self.config.base_url}/api/chat"
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": self.config.temperature},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise AIGenerationError(self._format_http_error(exc)) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise AIGenerationError(
                f"AI provider at {self.config.base_url} did not answer within {self.config.timeout} seconds. "
                "Ollama may still be running, but the response is too long or the model is too slow. "
                "Increase [AI] timeout or reduce the requested output."
            ) from exc
        except urllib.error.URLError as exc:
            raise AIGenerationError(
                f"Cannot reach AI provider at {self.config.base_url}. Make sure Ollama is running and reachable from this application."
            ) from exc
        except json.JSONDecodeError as exc:
            raise AIGenerationError("AI provider returned invalid JSON.") from exc
        message = data.get("message", {}) if isinstance(data, dict) else {}
        content = str(message.get("content") or data.get("response") or "").strip()
        if not content:
            raise AIGenerationError("AI provider returned an empty scenario.")
        return content


    def _format_http_error(self, exc: urllib.error.HTTPError) -> str:
        """Return an actionable message for Ollama HTTP errors."""
        detail = exc.reason or ""
        try:
            body = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""
        if body:
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                detail = body
            else:
                if isinstance(payload, dict):
                    detail = str(payload.get("error") or payload.get("message") or detail)
                else:
                    detail = str(payload)
        if exc.code == 404:
            suffix = f" Ollama said: {detail}" if detail else ""
            return (
                f"Ollama is reachable at {self.config.base_url}, but model '{self.config.model}' was not accepted."
                f" Verify the model name in AI settings or install it with: ollama pull {self.config.model}.{suffix}"
            )
        suffix = f" Response: {detail}" if detail else ""
        return f"AI provider at {self.config.base_url} returned HTTP {exc.code}.{suffix}"


class SafeFormatDict(dict):
    """Formatter mapping that leaves unknown placeholders visible."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def build_final_prompt(prompt: ScenarioPrompt, answers: Mapping[str, str]) -> tuple[str, list[str]]:
    """Build the final AI prompt and return unresolved placeholder warnings."""
    placeholders = extract_placeholders(prompt.prompt_text)
    missing = [name for name in placeholders if not str(answers.get(name, "")).strip()]
    formatted = prompt.prompt_text.format_map(SafeFormatDict({k: str(v) for k, v in answers.items()}))
    answer_lines = [f"- {question.label} ({question.key}): {answers.get(question.key, question.default)}" for question in prompt.questions]
    entity_schema_hint = (
        "\n\n# Entity output requirements\n"
        "When the scenario includes NPCs or Places, return them as structured JSON objects, "
        "not just prose fragments. NPC objects should include Name, Role, Description, "
        "Secret, Quote, RoleplayingCues, Personality, Motivation, Background, Traits, "
        "Factions, Objects, Portrait when known. Place objects should include Name, "
        "Description, NPCs, PlayerDisplay, Secrets, Portrait when known. The scenario's "
        "NPCs and Places may still be concise, but descriptions must contain usable GM content.\n"
    )
    final = f"{formatted}\n\n# Collected answers\n" + "\n".join(answer_lines) + entity_schema_hint
    return final, missing


def validate_required_answers(prompt: ScenarioPrompt, answers: Mapping[str, str]) -> list[str]:
    """Return labels for missing required answers."""
    missing: list[str] = []
    for question in prompt.questions:
        if question.required and not str(answers.get(question.key, question.default)).strip():
            missing.append(question.label)
    return missing


def parse_generated_scenario(text: str) -> dict[str, str | list[str]]:
    """Best-effort parser that extracts common scenario sections without crashing."""
    return normalize_generated_scenario_payload(text)


class AIScenarioGenerator:
    """Service layer for prompt-based AI scenario generation."""

    def __init__(self, provider: OllamaScenarioProvider | None = None):
        self.provider = provider or OllamaScenarioProvider()

    def generate(self, prompt: ScenarioPrompt, answers: Mapping[str, str]) -> str:
        """Generate a scenario from a stored prompt and user answers."""
        missing_required = validate_required_answers(prompt, answers)
        if missing_required:
            raise AIGenerationError("Missing required answers: " + ", ".join(missing_required))
        final_prompt, unresolved = build_final_prompt(prompt, answers)
        try:
            return self.provider.generate(final_prompt)
        except Exception:
            log_exception("AI scenario generation failed")
            raise
