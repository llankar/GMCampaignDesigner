"""Browser-backed AI client that automates a public chat UI."""

from __future__ import annotations

import atexit
import threading
import time
from pathlib import Path
from typing import Mapping, Sequence

from modules.ai.base_client import BaseAIClient
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import


log_module_import(__name__)


class WebAIClient(BaseAIClient):
    """Drive a browser session to relay prompts to a hosted chat UI."""

    def __init__(self):
        self.base_url = ConfigHelper.get(
            "AI", "web_url", fallback="https://chat.openai.com/"
        ) or "https://chat.openai.com/"
        self.conversation_url = (
            ConfigHelper.get("AI", "web_conversation_url", fallback=self.base_url)
            or self.base_url
        )
        self.prompt_selector = ConfigHelper.get(
            "AI", "web_prompt_selector", fallback="textarea"
        )
        self.submit_selector = ConfigHelper.get("AI", "web_submit_selector", fallback="")
        self.submit_keys = self._parse_keys(
            ConfigHelper.get("AI", "web_submit_keys", fallback="Enter")
        )
        self.response_selector = ConfigHelper.get(
            "AI",
            "web_response_selector",
            fallback="div[data-message-author-role='assistant']",
        )
        self.login_indicator_selector = ConfigHelper.get(
            "AI", "web_login_indicator_selector", fallback=""
        )
        self.storage_state_path = Path(
            ConfigHelper.get(
                "AI", "web_storage_state", fallback="config/web_ai_storage.json"
            )
        )
        self.browser_name = (
            ConfigHelper.get("AI", "web_browser", fallback="chromium") or "chromium"
        )
        headless_raw = ConfigHelper.get("AI", "web_headless", fallback="true")
        self.headless = str(headless_raw).strip().lower() in ("1", "true", "yes", "on")
        self.timeout_seconds = self._parse_int(
            ConfigHelper.get("AI", "web_timeout_seconds", fallback="120"),
            default=120,
        )
        self.refresh_each_call = str(
            ConfigHelper.get("AI", "web_reload_each_call", fallback="false")
        ).strip().lower() in ("1", "true", "yes", "on")
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = threading.RLock()
        atexit.register(self._shutdown)

    @staticmethod
    def _parse_keys(raw: str | None) -> list[str]:
        if not raw:
            return []
        parts = [item.strip() for item in raw.split(",")]
        return [p for p in parts if p]

    @staticmethod
    def _parse_int(raw: str | None, default: int) -> int:
        try:
            return int(str(raw).strip())
        except Exception:
            return default

    def _ensure_dependencies(self):
        if self._playwright is not None:
            return
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "The 'playwright' package is required for the web AI backend. "
                "Install it and run 'playwright install' to provision a browser."
            ) from exc
        self._playwright = sync_playwright().start()

    def _launch_browser(self, headless: bool):
        self._ensure_dependencies()
        browser_type = getattr(self._playwright, self.browser_name, None)
        if browser_type is None:
            raise RuntimeError(f"Unsupported browser type '{self.browser_name}'.")
        return browser_type.launch(headless=headless)

    def _shutdown(self):
        with self._lock:
            if self._page is not None:
                try:
                    self._page.close()
                except Exception:
                    pass
                self._page = None
            if self._context is not None:
                try:
                    self._context.close()
                except Exception:
                    pass
                self._context = None
            if self._browser is not None:
                try:
                    self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright is not None:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None

    def _invalidate_context(self):
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        self._context = None
        self._browser = None
        self._page = None

    def _ensure_context(self):
        if self._context is not None and not getattr(self._context, "is_closed", lambda: False)():
            return

        storage_state = None
        if self.storage_state_path.exists():
            storage_state = str(self.storage_state_path)
        else:
            self._interactive_login()
            if self.storage_state_path.exists():
                storage_state = str(self.storage_state_path)

        self._browser = self._launch_browser(headless=self.headless)
        self._context = self._browser.new_context(storage_state=storage_state)
        self._page = None

    def _interactive_login(self):
        self._ensure_dependencies()
        login_browser = self._launch_browser(headless=False)
        login_context = login_browser.new_context()
        page = login_context.new_page()
        page.goto(self.conversation_url, wait_until="load", timeout=self.timeout_seconds * 1000)
        print("WebAIClient: please complete login in the opened browser window.")
        try:
            input("Press Enter here once you are logged in...")
        except EOFError:
            # Non-interactive environment; wait a generous grace period.
            time.sleep(5)
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        login_context.storage_state(path=str(self.storage_state_path))
        try:
            login_context.close()
        except Exception:
            pass
        try:
            login_browser.close()
        except Exception:
            pass

    def _get_page(self):
        self._ensure_context()
        if self._context is None:
            raise RuntimeError("WebAIClient failed to initialize Playwright context")

        if self._page is None or getattr(self._page, "is_closed", lambda: False)():
            self._page = self._context.new_page()
            self._page.goto(
                self.conversation_url,
                wait_until="load",
                timeout=self.timeout_seconds * 1000,
            )

        if self.refresh_each_call:
            self._page.goto(
                self.conversation_url,
                wait_until="load",
                timeout=self.timeout_seconds * 1000,
            )

        if self.login_indicator_selector:
            try:
                indicator = self._page.query_selector(self.login_indicator_selector)
            except Exception:
                indicator = None
            if indicator:
                self._invalidate_context()
                self._interactive_login()
                return self._get_page()

        return self._page

    def _count_responses(self, page) -> int:
        try:
            elements = page.query_selector_all(self.response_selector)
            return len(elements or [])
        except Exception:
            return 0

    def _wait_for_new_response(self, page, baseline: int, timeout_seconds: int):
        try:
            page.wait_for_function(
                "(selector, baseline) => document.querySelectorAll(selector).length > baseline",
                self.response_selector,
                baseline,
                timeout=timeout_seconds * 1000,
            )
        except Exception as exc:
            raise RuntimeError("Timed out waiting for AI response") from exc

    def _extract_latest_response(self, page, timeout_seconds: int):
        elements = page.query_selector_all(self.response_selector)
        if not elements:
            raise RuntimeError("No response elements found on the page")
        element = elements[-1]
        text = ""
        stable = 0
        for _ in range(max(1, timeout_seconds * 2)):
            candidate = element.inner_text().strip()
            if candidate:
                if candidate == text:
                    stable += 1
                    if stable >= 3:
                        break
                else:
                    text = candidate
                    stable = 0
            time.sleep(0.5)
        return text.strip()

    def chat(
        self,
        messages: Sequence[Mapping[str, str]] | str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int = 600,
    ) -> str:
        prompt_text = BaseAIClient.format_messages(messages)

        with self._lock:
            page = self._get_page()
            if page is None:
                raise RuntimeError("WebAIClient could not open a page")

            wait_seconds = min(self.timeout_seconds, timeout) if timeout else self.timeout_seconds
            try:
                wait_seconds = max(1, int(wait_seconds))
            except Exception:
                wait_seconds = self.timeout_seconds
            try:
                field = page.wait_for_selector(
                    self.prompt_selector, timeout=wait_seconds * 1000
                )
            except Exception as exc:
                raise RuntimeError("Prompt field not found on the AI web page") from exc

            baseline = self._count_responses(page)

            try:
                field.click()
            except Exception:
                pass

            try:
                field.fill("")
            except Exception:
                pass

            try:
                field.type(prompt_text)
            except Exception:
                field.fill(prompt_text)

            if self.submit_selector:
                page.click(self.submit_selector)
            elif self.submit_keys:
                for key in self.submit_keys:
                    page.keyboard.press(key)
            else:
                page.keyboard.press("Enter")

            self._wait_for_new_response(page, baseline, wait_seconds)
            response_text = self._extract_latest_response(page, wait_seconds)
            if not response_text:
                raise RuntimeError("Empty response scraped from AI web page")
            return response_text

