"""Persistent AI prompt library for scenario generation."""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from string import Formatter
from typing import Any

from modules.helpers.config_helper import ConfigHelper

_PLACEHOLDER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PromptLibraryError(ValueError):
    """Raised when prompt library data is invalid."""


@dataclass
class PromptQuestion:
    """Question used to collect a placeholder value from the user."""

    key: str
    label: str
    required: bool = True
    default: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PromptQuestion":
        """Create a question from a JSON-compatible dictionary."""
        key = str(payload.get("key") or payload.get("placeholder") or "").strip()
        label = str(payload.get("label") or payload.get("question") or key).strip()
        return cls(
            key=key,
            label=label,
            required=bool(payload.get("required", True)),
            default=str(payload.get("default", "")),
        )


@dataclass
class ScenarioPrompt:
    """Stored reusable scenario-generation prompt."""

    id: str
    name: str
    description: str
    category: str
    prompt_text: str
    questions: list[PromptQuestion] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def new(
        cls,
        name: str,
        description: str,
        category: str,
        prompt_text: str,
        questions: list[PromptQuestion],
    ) -> "ScenarioPrompt":
        """Create a new prompt with generated identity and timestamps."""
        now = _utc_now()
        return cls(str(uuid.uuid4()), name, description, category, prompt_text, questions, now, now)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScenarioPrompt":
        """Create a prompt from a JSON-compatible dictionary."""
        questions = [PromptQuestion.from_dict(q) for q in payload.get("questions", []) if isinstance(q, dict)]
        now = _utc_now()
        return cls(
            id=str(payload.get("id") or uuid.uuid4()),
            name=str(payload.get("name") or "").strip(),
            description=str(payload.get("description") or ""),
            category=str(payload.get("category") or payload.get("genre") or ""),
            prompt_text=str(payload.get("prompt_text") or ""),
            questions=questions,
            created_at=str(payload.get("created_at") or now),
            updated_at=str(payload.get("updated_at") or now),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_prompt_library_path() -> Path:
    """Return the prompt library JSON path in the campaign/config area."""
    campaign_dir = Path(ConfigHelper.get_campaign_dir())
    if str(campaign_dir) in {"", "."}:
        campaign_dir = Path("config")
    return campaign_dir / "scenario_prompt_library.json"


def extract_placeholders(prompt_text: str) -> list[str]:
    """Extract valid Python-format placeholders from prompt text."""
    names: list[str] = []
    for _, field_name, _, _ in Formatter().parse(prompt_text or ""):
        if not field_name:
            continue
        name = field_name.split(".", 1)[0].split("[", 1)[0]
        if _PLACEHOLDER_RE.match(name) and name not in names:
            names.append(name)
    return names


def validate_prompt(prompt: ScenarioPrompt, existing: list[ScenarioPrompt] | None = None) -> list[str]:
    """Return validation errors for a prompt."""
    errors: list[str] = []
    if not prompt.name.strip():
        errors.append("Prompt name is required.")
    if not prompt.prompt_text.strip():
        errors.append("Prompt text is required.")
    if existing:
        lowered = prompt.name.strip().lower()
        if any(p.id != prompt.id and p.name.strip().lower() == lowered for p in existing):
            errors.append(f"A prompt named '{prompt.name}' already exists.")
    for question in prompt.questions:
        if not question.key.strip():
            errors.append("Every question needs a placeholder key.")
        elif not _PLACEHOLDER_RE.match(question.key.strip()):
            errors.append(f"Invalid placeholder key: {question.key}")
        if not question.label.strip():
            errors.append(f"Question '{question.key}' needs a label.")
    return errors


DEFAULT_PROMPT_NAME = "Professional RPG Scenario"
DEFAULT_PROMPT_DESCRIPTION = "Industry-style prompt for a complete, playable RPG scenario."
DEFAULT_PROMPT_CATEGORY = "Generic RPG"
LEGACY_DEFAULT_OPTIONAL_QUESTION_KEYS = {
    "tone",
    "party_level",
    "system",
    "additional_constraints",
}


def _normalized_question_keys(questions: list[PromptQuestion]) -> set[str]:
    """Return normalized question keys for identity and migration checks."""
    return {question.key.strip().casefold() for question in questions}


def default_prompt_questions() -> list[PromptQuestion]:
    """Return the current question flow for the built-in default prompt."""
    return [
        PromptQuestion(
            "scenario_type",
            "Type or background (medfan, sci-fi, modern, Star Wars, Dresden Files, Dragonlance...)",
            True,
        ),
        PromptQuestion("theme", "Theme of the scenario", True),
        PromptQuestion("location", "Location of the scenario", True),
    ]


DEFAULT_PROMPT_TEXT = """# Role
You are a professional RPG scenario writer working in the RPG industry. Your style is original, witty, sensory, mysterious, and immediately usable at the table. Use strong hooks, meaningful NPC motives, scene escalation, player agency, secrets, revelations, and playable conflicts.

# User answers
- Type or background: {scenario_type}
- Theme: {theme}
- Location: {location}
- Tone: cinematic, mysterious, and playable
- Power scale: appropriate for the campaign
- System: system-neutral unless implied by the background
- Constraints: none unless implied by the user answers

# Rules
1. Reread, criticize, and improve your own scenario before giving the final answer.
2. Use the five senses in descriptions when useful: sight, sound, smell, touch, taste.
3. Create original NPCs with physical descriptions, short backgrounds, and clear motives.
4. Create at least 3 personal ways to connect the player characters to the scenario.
5. Include at least 3 scenes. Each scene clearly lists its locations, NPCs, and each NPC's role.
6. Every important location is original and fully described. If combat can happen there, include tactical features such as height, holes, fire, moving machinery, unstable ground, crowds, darkness, water, vehicles, traps, or cover.
7. The main scenario summary is 8 short lines maximum.
8. NPCs and locations appear after the summary and do not count toward those 8 lines.
9. Each NPC is 3 lines maximum. Each location is 3 lines maximum.
10. Every important detail for an NPC, scene, or place is written as an “Atout”, like Savage/Fate-style RPG tags.
11. Use every rule in every generated scenario.

# Required output format
Title:
Pitch:
Scenario Summary, maximum 8 short lines:
Scenes:
Scene 1:
* Purpose:
* Location:
* NPCs:
* Atouts:
Scene 2:
* Purpose:
* Location:
* NPCs:
* Atouts:
Scene 3:
* Purpose:
* Location:
* NPCs:
* Atouts:
NPCs:
Locations:
PC Connections:
Secrets and Twists:
Atouts Summary:
GM Notes:
"""


def default_prompts() -> list[ScenarioPrompt]:
    """Return built-in prompts used to seed or restore the library."""
    return [
        ScenarioPrompt.new(
            name=DEFAULT_PROMPT_NAME,
            description=DEFAULT_PROMPT_DESCRIPTION,
            category=DEFAULT_PROMPT_CATEGORY,
            prompt_text=DEFAULT_PROMPT_TEXT,
            questions=default_prompt_questions(),
        )
    ]


def _is_builtin_default_prompt(prompt: ScenarioPrompt) -> bool:
    """Return whether a prompt clearly identifies the built-in default prompt."""
    name_matches = prompt.name.strip().casefold() == DEFAULT_PROMPT_NAME.casefold()
    metadata_matches = (
        prompt.category.strip().casefold() == DEFAULT_PROMPT_CATEGORY.casefold()
        and prompt.description.strip().casefold() == DEFAULT_PROMPT_DESCRIPTION.casefold()
    )
    return name_matches or metadata_matches


class PromptLibrary:
    """Load, validate, save, import, and export scenario prompts."""

    def __init__(self, path: Path | None = None):
        self.path = path or get_prompt_library_path()

    def load(self) -> list[ScenarioPrompt]:
        """Load prompts, seeding defaults when no library exists."""
        if not self.path.exists():
            prompts = default_prompts()
            self.save(prompts)
            return prompts
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PromptLibraryError(f"Invalid prompt library JSON: {exc}") from exc
        items = raw.get("prompts", raw) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            raise PromptLibraryError("Prompt library JSON must contain a list of prompts.")
        prompts = [ScenarioPrompt.from_dict(item) for item in items if isinstance(item, dict)]
        if not prompts:
            prompts = default_prompts()
            self.save(prompts)
        elif self._migrate_builtin_default_questions(prompts):
            self.save(prompts)
        return prompts

    def _migrate_builtin_default_questions(self, prompts: list[ScenarioPrompt]) -> bool:
        """Normalize legacy built-in default prompts to the current three-question flow."""
        migrated = False
        for prompt in prompts:
            if not _is_builtin_default_prompt(prompt):
                continue
            question_keys = _normalized_question_keys(prompt.questions)
            if not question_keys.intersection(LEGACY_DEFAULT_OPTIONAL_QUESTION_KEYS):
                continue
            prompt.questions = default_prompt_questions()
            prompt.updated_at = _utc_now()
            migrated = True
        return migrated

    def save(self, prompts: list[ScenarioPrompt]) -> None:
        """Persist prompts to JSON."""
        names: list[str] = []
        for prompt in prompts:
            errors = validate_prompt(prompt, [p for p in prompts if p is not prompt])
            if errors:
                raise PromptLibraryError("\n".join(errors))
            name_key = prompt.name.strip().lower()
            if name_key in names:
                raise PromptLibraryError(f"Duplicate prompt name: {prompt.name}")
            names.append(name_key)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "prompts": [prompt.to_dict() for prompt in prompts]}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def import_from_file(self, source: str | Path, merge: bool = True) -> list[ScenarioPrompt]:
        """Import prompts from JSON and return the saved library."""
        try:
            raw = json.loads(Path(source).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PromptLibraryError(f"Invalid JSON import: {exc}") from exc
        items = raw.get("prompts", raw) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            raise PromptLibraryError("Imported JSON must contain a list of prompts.")
        imported = [ScenarioPrompt.from_dict(item) for item in items if isinstance(item, dict)]
        existing = self.load() if merge else []
        by_name = {p.name.strip().lower(): p for p in existing}
        for prompt in imported:
            prompt.id = str(uuid.uuid4()) if prompt.name.strip().lower() in by_name else prompt.id
            prompt.updated_at = _utc_now()
            by_name[prompt.name.strip().lower()] = prompt
        prompts = list(by_name.values())
        self.save(prompts)
        return prompts

    def export_to_file(self, prompts: list[ScenarioPrompt], target: str | Path) -> None:
        """Export prompts to JSON."""
        Path(target).write_text(
            json.dumps({"version": 1, "prompts": [p.to_dict() for p in prompts]}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def restore_defaults(self, keep_existing: bool = False) -> list[ScenarioPrompt]:
        """Restore built-in prompts, optionally keeping custom prompts."""
        prompts = self.load() if keep_existing and self.path.exists() else []
        existing_names = {p.name.strip().lower() for p in prompts}
        for prompt in default_prompts():
            if prompt.name.strip().lower() not in existing_names:
                prompts.append(prompt)
        if not keep_existing:
            prompts = default_prompts()
        self.save(prompts)
        return prompts
