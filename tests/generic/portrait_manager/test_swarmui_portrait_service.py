"""Tests for the UI-independent SwarmUI portrait service."""
from __future__ import annotations

import base64

from modules.helpers import swarmui_portrait_service
from modules.helpers.swarmui_portrait_service import (
    SWARM_API_URL,
    PortraitGenerationSource,
    SwarmUIPortraitSettings,
    build_portrait_prompt,
    create_generated_portrait_filename,
    generate_portrait_candidates,
)


class FakeResponse:
    def __init__(self, *, payload=None, content: bytes = b""):
        self._payload = payload or {}
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class FakeHttpClient:
    def __init__(self, image_bytes: bytes):
        self.image_bytes = image_bytes
        self.posts = []
        self.gets = []

    def post(self, url: str, **kwargs):
        self.posts.append((url, kwargs))
        if url.endswith("/API/GetNewSession"):
            return FakeResponse(payload={"session_id": "session-1"})
        if url.endswith("/API/GenerateText2Image"):
            return FakeResponse(payload={"images": ["View/local/image.png"]})
        raise AssertionError(f"Unexpected POST URL: {url}")

    def get(self, url: str, **kwargs):
        self.gets.append((url, kwargs))
        return FakeResponse(content=self.image_bytes)


def _png_bytes() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKklEQVR4nO3OQQ0AIBDAsAP/nuGNAvZoFSzZOjNnyNi/AwAAAAAAAAAAXgOShgHBiIFQyQAAAABJRU5ErkJggg=="
    )


def test_generate_portrait_candidates_uses_mocked_swarmui_http_client(monkeypatch) -> None:
    http_client = FakeHttpClient(_png_bytes())
    source = PortraitGenerationSource(
        name="Captain Test",
        record={"Name": "Captain Test", "Description": "A brave pilot", "Role": "Ace"},
    )
    settings = SwarmUIPortraitSettings(model="test-model", image_count=2, cfgscale=7.5)
    monkeypatch.setattr(swarmui_portrait_service, "make_thumbnail", lambda content: "thumbnail")

    candidates = generate_portrait_candidates(source, settings, http_client=http_client)

    assert len(candidates) == 1
    assert candidates[0].image_bytes == http_client.image_bytes
    assert candidates[0].thumbnail == "thumbnail"
    assert http_client.posts[0][0] == f"{SWARM_API_URL}/API/GetNewSession"
    generate_url, generate_kwargs = http_client.posts[1]
    assert generate_url == f"{SWARM_API_URL}/API/GenerateText2Image"
    assert generate_kwargs["json"]["session_id"] == "session-1"
    assert generate_kwargs["json"]["prompt"] == "Captain Test A brave pilot Ace"
    assert generate_kwargs["json"]["images"] == 2
    assert generate_kwargs["json"]["model"] == "test-model"
    assert http_client.gets[0][0] == f"{SWARM_API_URL}/View/local/image.png"


def test_prompt_and_filename_helpers_are_safe_and_reusable() -> None:
    source = PortraitGenerationSource(
        name="Unsafe / Name",
        record={"Name": "Unsafe / Name", "Portrait": "ignored", "Description": "Useful text"},
    )

    assert build_portrait_prompt(source, prompt_fields=["Portrait", "Description"]) == "Useful text"
    assert create_generated_portrait_filename("Unsafe / Name").startswith("Unsafe_Name_portrait_")
