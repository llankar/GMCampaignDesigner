"""Tests for AI prompt library and scenario generation helpers."""


import pytest

from modules.scenarios.ai_prompt_library import (
    PromptLibrary,
    PromptLibraryError,
    PromptQuestion,
    ScenarioPrompt,
    extract_placeholders,
    validate_prompt,
)
from modules.scenarios.ai_scenario_generator import (
    AIProviderConfig,
    OllamaScenarioProvider,
    build_final_prompt,
    parse_generated_scenario,
    validate_required_answers,
)


def test_extract_placeholders_ignores_duplicates_and_invalid_format_parts():
    assert extract_placeholders("Use {theme} in {location}. Again {theme} and {npc.name}.") == ["theme", "location", "npc"]


def test_validate_prompt_requires_name_text_and_unique_names():
    prompt = ScenarioPrompt.new("", "", "", "", [])
    existing = [ScenarioPrompt.new("Existing", "", "", "Text", [])]
    duplicate = ScenarioPrompt.new("Existing", "", "", "Text", [])
    errors = validate_prompt(prompt, existing)
    assert "Prompt name is required." in errors
    assert "Prompt text is required." in errors
    assert validate_prompt(duplicate, existing) == ["A prompt named 'Existing' already exists."]


def test_prompt_library_load_save_import_export_roundtrip(tmp_path):
    library = PromptLibrary(tmp_path / "prompts.json")
    prompt = ScenarioPrompt.new("Mystery", "Desc", "Modern", "Write {theme}", [PromptQuestion("theme", "Theme")])
    library.save([prompt])
    loaded = library.load()
    assert loaded[0].name == "Mystery"
    exported = tmp_path / "export.json"
    library.export_to_file(loaded, exported)
    imported_library = PromptLibrary(tmp_path / "imported.json")
    imported = imported_library.import_from_file(exported, merge=False)
    assert imported[0].questions[0].key == "theme"


def test_prompt_library_migrates_legacy_builtin_default_questions(tmp_path):
    library = PromptLibrary(tmp_path / "prompts.json")
    legacy_prompt = ScenarioPrompt.new(
        "Professional RPG Scenario",
        "Industry-style prompt for a complete, playable RPG scenario.",
        "Generic RPG",
        "Write {scenario_type} {theme} {location}",
        [
            PromptQuestion("scenario_type", "Type"),
            PromptQuestion("theme", "Theme"),
            PromptQuestion("location", "Location"),
            PromptQuestion("Tone", "Tone", False),
            PromptQuestion("party_level", "Party level", False),
            PromptQuestion("system", "System", False),
            PromptQuestion("additional_constraints", "Additional constraints", False),
        ],
    )
    custom_prompt = ScenarioPrompt.new(
        "Custom Scenario",
        "Custom prompt that happens to use legacy-style optional questions.",
        "Generic RPG",
        "Write {scenario_type} {tone}",
        [PromptQuestion("scenario_type", "Type"), PromptQuestion("tone", "Tone", False)],
    )
    library.save([legacy_prompt, custom_prompt])

    loaded = library.load()

    assert [question.key for question in loaded[0].questions] == ["scenario_type", "theme", "location"]
    assert [question.key for question in loaded[1].questions] == ["scenario_type", "tone"]

    reloaded = PromptLibrary(tmp_path / "prompts.json").load()
    assert [question.key for question in reloaded[0].questions] == ["scenario_type", "theme", "location"]


def test_prompt_library_migrates_builtin_default_by_known_metadata(tmp_path):
    library = PromptLibrary(tmp_path / "prompts.json")
    legacy_prompt = ScenarioPrompt.new(
        "Renamed Default",
        "Industry-style prompt for a complete, playable RPG scenario.",
        "Generic RPG",
        "Write {scenario_type} {theme} {location}",
        [
            PromptQuestion("scenario_type", "Type"),
            PromptQuestion("additional_constraints", "Additional constraints", False),
        ],
    )
    library.save([legacy_prompt])

    loaded = library.load()

    assert [question.key for question in loaded[0].questions] == ["scenario_type", "theme", "location"]


def test_prompt_library_migrates_builtin_default_prompt_text_placeholders(tmp_path):
    library = PromptLibrary(tmp_path / "prompts.json")
    legacy_prompt = ScenarioPrompt.new(
        "Professional RPG Scenario",
        "Industry-style prompt for a complete, playable RPG scenario.",
        "Generic RPG",
        "Write {scenario_type} {tone} {party_level} {system} {additional_constraints}",
        [
            PromptQuestion("scenario_type", "Type"),
            PromptQuestion("theme", "Theme"),
            PromptQuestion("location", "Location"),
        ],
    )
    library.save([legacy_prompt])

    loaded = library.load()
    _final, unresolved = build_final_prompt(
        loaded[0],
        {"scenario_type": "medfan", "theme": "betrayal", "location": "old abbey"},
    )

    assert unresolved == []
    assert [question.key for question in loaded[0].questions] == ["scenario_type", "theme", "location"]

def test_prompt_library_rejects_invalid_json_import(tmp_path):
    library = PromptLibrary(tmp_path / "prompts.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(PromptLibraryError):
        library.import_from_file(bad)


def test_build_final_prompt_and_required_answers():
    prompt = ScenarioPrompt.new(
        "Prompt",
        "",
        "",
        "Type {scenario_type}; theme {theme}; unknown {unknown}",
        [PromptQuestion("scenario_type", "Type"), PromptQuestion("theme", "Theme")],
    )
    assert validate_required_answers(prompt, {"scenario_type": "fantasy"}) == ["Theme"]
    final, unresolved = build_final_prompt(prompt, {"scenario_type": "fantasy", "theme": "betrayal"})
    assert "Type fantasy" in final
    assert unresolved == ["unknown"]


def test_parse_generated_scenario_sections_best_effort():
    text = """Title: The Ash Bell
Scenario Summary, maximum 8 short lines:
A bell wakes the dead.
Secrets and Twists:
The priest is the bell.
NPCs:
- Mara, ash-smudged smith
Locations:
- The cracked belfry
"""
    parsed = parse_generated_scenario(text)
    assert parsed["Title"] == "The Ash Bell"
    assert parsed["Secrets"] == "The priest is the bell."
    assert parsed["NPCs"] == ["Mara, ash-smudged smith"]
    assert parsed["Places"] == ["The cracked belfry"]


def test_ollama_provider_reports_unreachable_provider(monkeypatch):
    from modules.scenarios import ai_scenario_generator as generator

    provider = generator.OllamaScenarioProvider(
        generator.AIProviderConfig(base_url="http://127.0.0.1:11434", model="gpt-oss:20b")
    )

    def raise_url_error(*_args, **_kwargs):
        raise generator.urllib.error.URLError("connection refused")

    monkeypatch.setattr(generator.urllib.request, "urlopen", raise_url_error)

    with pytest.raises(generator.AIGenerationError) as excinfo:
        provider.generate("hello")

    assert "Cannot reach AI provider" in str(excinfo.value)
    assert "model" not in str(excinfo.value).lower()


def test_ollama_provider_reports_socket_timeout_as_timeout(monkeypatch):
    import socket

    from modules.scenarios import ai_scenario_generator as generator

    provider = generator.OllamaScenarioProvider(
        generator.AIProviderConfig(base_url="http://127.0.0.1:11434", model="gpt-oss:20b", timeout=5)
    )

    def raise_socket_timeout(*_args, **_kwargs):
        raise socket.timeout("timed out")

    monkeypatch.setattr(generator.urllib.request, "urlopen", raise_socket_timeout)

    with pytest.raises(generator.AIGenerationError) as excinfo:
        provider.generate("hello")

    message = str(excinfo.value)
    assert "did not answer within 5 seconds" in message
    assert "timeout" in message
    assert "Cannot reach AI provider" not in message

def test_ollama_provider_reports_model_http_error(monkeypatch):
    from io import BytesIO
    from modules.scenarios import ai_scenario_generator as generator

    provider = generator.OllamaScenarioProvider(
        generator.AIProviderConfig(base_url="http://127.0.0.1:11434", model="gpt-oss:20b")
    )

    def raise_http_error(*_args, **_kwargs):
        raise generator.urllib.error.HTTPError(
            "http://127.0.0.1:11434/api/chat",
            404,
            "Not Found",
            hdrs=None,
            fp=BytesIO(b'{"error":"model \\"gpt-oss:20b\\" not found"}'),
        )

    monkeypatch.setattr(generator.urllib.request, "urlopen", raise_http_error)

    with pytest.raises(generator.AIGenerationError) as excinfo:
        provider.generate("hello")

    message = str(excinfo.value)
    assert "Ollama is reachable" in message
    assert "ollama pull gpt-oss:20b" in message
    assert "model" in message


class _FakeOllamaResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"message": {"content": "Generated scenario"}}'

    def __iter__(self):
        return iter([b'{"message": {"content": "Generated scenario"}}\n'])


class _FakeStreamingOllamaResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter([
            b'{"message": {"content": "The Ash "}}\n',
            b'\n',
            b'{"message": {"content": "Bell"}}\n',
            b'{"done": true}\n',
        ])


def test_ollama_provider_stitches_newline_delimited_streaming_chunks(monkeypatch):
    from modules.scenarios import ai_scenario_generator as generator

    captured_payloads = []
    provider = OllamaScenarioProvider(AIProviderConfig(stream=True))

    def fake_urlopen(request, **_kwargs):
        captured_payloads.append(generator.json.loads(request.data.decode("utf-8")))
        return _FakeStreamingOllamaResponse()

    monkeypatch.setattr(generator.urllib.request, "urlopen", fake_urlopen)

    assert provider.generate("hello") == "The Ash Bell"
    assert captured_payloads[0]["stream"] is True


def test_ollama_provider_keeps_non_streaming_mode_when_disabled(monkeypatch):
    from modules.scenarios import ai_scenario_generator as generator

    captured_payloads = []
    provider = OllamaScenarioProvider(AIProviderConfig(stream=False))

    def fake_urlopen(request, **_kwargs):
        captured_payloads.append(generator.json.loads(request.data.decode("utf-8")))
        return _FakeOllamaResponse()

    monkeypatch.setattr(generator.urllib.request, "urlopen", fake_urlopen)

    assert provider.generate("hello") == "Generated scenario"
    assert captured_payloads[0]["stream"] is False


def test_ollama_provider_sends_positive_max_tokens_as_num_predict(monkeypatch):
    from modules.scenarios import ai_scenario_generator as generator

    captured_payloads = []
    provider = OllamaScenarioProvider(AIProviderConfig(max_tokens=512))

    def fake_urlopen(request, **_kwargs):
        captured_payloads.append(generator.json.loads(request.data.decode("utf-8")))
        return _FakeOllamaResponse()

    monkeypatch.setattr(generator.urllib.request, "urlopen", fake_urlopen)

    assert provider.generate("hello") == "Generated scenario"
    assert captured_payloads[0]["options"]["num_predict"] == 512


@pytest.mark.parametrize("max_tokens", [0, -25])
def test_ollama_provider_omits_non_positive_max_tokens(monkeypatch, max_tokens):
    from modules.scenarios import ai_scenario_generator as generator

    captured_payloads = []
    provider = OllamaScenarioProvider(AIProviderConfig(max_tokens=max_tokens))

    def fake_urlopen(request, **_kwargs):
        captured_payloads.append(generator.json.loads(request.data.decode("utf-8")))
        return _FakeOllamaResponse()

    monkeypatch.setattr(generator.urllib.request, "urlopen", fake_urlopen)

    assert provider.generate("hello") == "Generated scenario"
    assert "num_predict" not in captured_payloads[0]["options"]


def test_ai_provider_config_defaults_invalid_max_tokens_to_zero(monkeypatch):
    from modules.scenarios import ai_scenario_generator as generator

    def fake_get(_section, key, fallback=None):
        values = {
            "base_url": "http://example.test/",
            "model": "test-model",
            "temperature": "0.3",
            "timeout": "10",
            "max_tokens": "not-an-int",
            "stream": "false",
        }
        return values.get(key, fallback)

    monkeypatch.setattr(generator.ConfigHelper, "get", fake_get)

    config = AIProviderConfig.from_config()

    assert config.max_tokens == 0


def test_ollama_provider_generates_with_invalid_configured_max_tokens(monkeypatch):
    from modules.scenarios import ai_scenario_generator as generator

    captured_payloads = []

    def fake_get(_section, key, fallback=None):
        values = {
            "base_url": "http://example.test/",
            "model": "test-model",
            "temperature": "0.3",
            "timeout": "10",
            "max_tokens": "invalid",
            "stream": "false",
        }
        return values.get(key, fallback)

    def fake_urlopen(request, **_kwargs):
        captured_payloads.append(generator.json.loads(request.data.decode("utf-8")))
        return _FakeOllamaResponse()

    monkeypatch.setattr(generator.ConfigHelper, "get", fake_get)
    monkeypatch.setattr(generator.urllib.request, "urlopen", fake_urlopen)

    provider = OllamaScenarioProvider()

    assert provider.generate("hello") == "Generated scenario"
    assert provider.config.max_tokens == 0
    assert "num_predict" not in captured_payloads[0]["options"]


def test_parse_generated_scenario_extracts_fenced_entity_json_after_scenes():
    text = '''Title: Neon Feud
Summary: Corporate lovers race the city.

## Scene 1: Rooftop
Purpose: Establish danger.
  - Jax Shade (Elysium hacker) – determined.

## Scene 2: Subway
Purpose: Flight through the city.

## Scene 3: Holo-Bridge
Purpose: Final showdown.
Atouts: Bridge Collapse, Laser Traps.

---

## NPCs (JSON)

```json
[
  {
    "Name": "Jax \\\"Shade\\\" Kade",
    "Role": "Elysium Syndicate hacker",
    "Description": "Mid-30s, trench coat, cybernetic eye.",
    "Secret": "He engineered the Core hack.",
    "Quote": "In a city of neon, love is still code.",
    "RoleplayingCues": ["checks wrist implant constantly"],
    "Personality": "Skeptical, witty",
    "Motivation": "Escape corporate shackles",
    "Background": "Former Elysium tech.",
    "Traits": ["Tech Savvy"],
    "Factions": ["Elysium Syndicate (Former)"],
    "Objects": ["Neural chip"],
    "Portrait": null
  },
  {
    "Name": "Liora Voss",
    "Role": "Nebula Consortium heir",
    "Description": "Early 20s, silver hair.",
    "Secret": "She sabotaged the Core.",
    "Portrait": null
  }
]
```

---

## Locations (JSON)

```json
[
  {
    "Name": "Central Holo-Bridge",
    "Description": "Suspended over traffic and laser grids.",
    "NPCs": ["Jax \\\"Shade\\\" Kade", "Liora Voss"],
    "PlayerDisplay": "The air crackles with static.",
    "Secrets": ["A hidden control room lies beneath the bridge."],
    "Portrait": null
  }
]
```
'''

    parsed = parse_generated_scenario(text)

    assert [npc["Name"] for npc in parsed["NPCs"]] == [
        'Jax "Shade" Kade',
        "Liora Voss",
    ]
    assert parsed["NPCs"][0]["Role"] == "Elysium Syndicate hacker"
    assert [place["Name"] for place in parsed["Places"]] == ["Central Holo-Bridge"]
    assert len(parsed["Scenes"]) == 3
    assert "NPCs (JSON)" not in parsed["Scenes"][-1]["Text"]
    assert "Locations (JSON)" not in parsed["Scenes"][-1]["Text"]
