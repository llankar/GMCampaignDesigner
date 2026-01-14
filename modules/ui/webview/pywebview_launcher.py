"""Standalone entrypoint for opening a pywebview window."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import webview

from modules.helpers.logging_helper import log_info, log_module_import

log_module_import(__name__)

_CONTENT_SHELL_JS = """
(function () {
  if (window.__pywebview_shell_ready) {
    return;
  }
  window.__pywebview_shell_ready = true;
  window.__pywebview_last_selection = "";
  window.__pywebview_last_url = "";

  let addressInput = null;
  let goButton = null;
  let importButton = null;
  let status = null;

  const setStatus = (message, isError = false) => {
    if (!status) {
      return;
    }
    status.textContent = message;
    status.style.color = isError ? "#ff9b9b" : "#9fa6b2";
  };

  const enableSelection = () => {
    if (document.getElementById("__pywebview_shell_style")) {
      return;
    }
    const style = document.createElement("style");
    style.id = "__pywebview_shell_style";
    style.textContent =
      "* { -webkit-user-select: text !important; user-select: text !important; }";
    (document.head || document.documentElement).appendChild(style);
  };

  const updateSelection = () => {
    const selection = window.getSelection ? window.getSelection().toString() : "";
    const trimmed = selection.trim();
    if (!trimmed || trimmed === window.__pywebview_last_selection) {
      return;
    }
    window.__pywebview_last_selection = trimmed;
    window.__pywebview_last_url = window.location.href || "";
    setStatus("Selection cached.");
    if (window.pywebview && window.pywebview.api && window.pywebview.api.cache_selection) {
      window.pywebview.api.cache_selection(trimmed, window.__pywebview_last_url);
    }
  };

  const doImport = () => {
    const selection = window.__pywebview_last_selection || "";
    if (!selection) {
      setStatus("Selection empty.", true);
      return;
    }
    const url = window.__pywebview_last_url || window.location.href || "";
    if (window.pywebview && window.pywebview.api && window.pywebview.api.import_selection) {
      window.pywebview.api.import_selection(selection, url).then((response) => {
        if (response && response.ok === false) {
          setStatus(response.message || "Unable to send selection.", true);
        } else {
          setStatus("Selection sent.");
        }
      });
    } else {
      setStatus("API unavailable.", true);
    }
  };

  const navigateTo = (url) => {
    if (!url) {
      setStatus("Missing address.", true);
      return;
    }
    setStatus("Opening page...");
    window.location.assign(url);
  };

  const buildShell = () => {
    if (document.getElementById("__pywebview_shell")) {
      return;
    }
    const mount = document.body || document.documentElement;
    if (!mount) {
      return;
    }
    enableSelection();
    const container = document.createElement("div");
    container.id = "__pywebview_shell";
    container.style.position = "fixed";
    container.style.top = "16px";
    container.style.right = "16px";
    container.style.zIndex = "2147483647";
    container.style.background = "rgba(20, 24, 34, 0.94)";
    container.style.color = "#f5f6fa";
    container.style.border = "1px solid rgba(255, 255, 255, 0.12)";
    container.style.borderRadius = "10px";
    container.style.padding = "10px";
    container.style.fontFamily = "Segoe UI, Arial, sans-serif";
    container.style.fontSize = "13px";
    container.style.minWidth = "280px";
    container.style.boxShadow = "0 12px 30px rgba(0, 0, 0, 0.35)";

    container.innerHTML = `
      <div style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">
        <span style="font-size:11px; letter-spacing:0.04em; color:#9fa6b2;">ADDRESS</span>
        <input id="__pywebview_shell_address" type="text"
          style="flex:1; padding:6px 8px; border-radius:6px; border:1px solid rgba(255, 255, 255, 0.12); background:#0f131b; color:#f5f6fa;" />
        <button id="__pywebview_shell_go" type="button"
          style="padding:6px 10px; border-radius:6px; border:1px solid rgba(255, 255, 255, 0.12); background:transparent; color:#f5f6fa; cursor:pointer;">Go</button>
      </div>
      <div style="display:flex; gap:8px; align-items:center;">
        <span id="__pywebview_shell_status" style="flex:1; color:#9fa6b2;">Select text, then Import.</span>
        <button id="__pywebview_shell_import" type="button"
          style="padding:6px 12px; border-radius:6px; border:1px solid transparent; background:#5b8def; color:#fdfdff; cursor:pointer;">Import</button>
      </div>
      <div style="margin-top:6px; font-size:11px; color:#9fa6b2;">Shortcut: Ctrl+Shift+I</div>
    `;

    mount.appendChild(container);

    addressInput = container.querySelector("#__pywebview_shell_address");
    goButton = container.querySelector("#__pywebview_shell_go");
    importButton = container.querySelector("#__pywebview_shell_import");
    status = container.querySelector("#__pywebview_shell_status");
    addressInput.value = window.location.href || "";

    addressInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        navigateTo(addressInput.value.trim());
      }
    });

    goButton.addEventListener("click", () => {
      navigateTo(addressInput.value.trim());
    });

    importButton.addEventListener("click", () => {
      doImport();
    });
  };

  const attachListeners = () => {
    if (window.__pywebview_shell_listeners) {
      return;
    }
    window.__pywebview_shell_listeners = true;
    document.addEventListener("selectionchange", updateSelection);
    document.addEventListener("mouseup", updateSelection);
    document.addEventListener("keyup", updateSelection);
    document.addEventListener("keydown", (event) => {
      if (event.ctrlKey && event.shiftKey && (event.key === "I" || event.key === "i")) {
        event.preventDefault();
        doImport();
      }
    });
  };

  const init = () => {
    buildShell();
    attachListeners();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
"""


@dataclass(slots=True)
class BrowserShellApi:
    selection_output: str | None = None
    target_url: str = ""
    _content_window: object | None = None
    _last_selection: str = ""
    _last_url: str = ""

    def get_initial_target(self) -> str:
        return self.target_url

    def cache_selection(self, selection: str, url: str) -> None:
        selection_text = (selection or "").strip()
        if not selection_text:
            return
        self._last_selection = selection_text
        self._last_url = (url or "").strip()

    def navigate(self, url: str) -> dict:
        if not url:
            return {"ok": False, "message": "Missing address."}
        if not self._content_window:
            return {"ok": False, "message": "Browser window not ready."}
        try:
            self._content_window.load_url(url)
            self._last_selection = ""
            self._last_url = url.strip()
        except Exception as exc:
            log_info(
                f"Unable to navigate to {url}: {exc}",
                func_name="BrowserShellApi.navigate",
            )
            return {"ok": False, "message": "Unable to open address."}
        return {"ok": True}

    def import_selection(self, selection: str | None = None, url: str | None = None) -> dict:
        selection_text = (selection or "").strip()
        current_url = (url or "").strip()
        if self._content_window and (not selection_text or not current_url):
            try:
                if not selection_text:
                    selection_text = (
                        self._content_window.evaluate_js(
                            "window.getSelection().toString()"
                        )
                        or ""
                    ).strip()
                if not current_url:
                    current_url = (self._content_window.get_current_url() or "").strip()
            except Exception as exc:
                log_info(
                    f"Unable to read selection: {exc}",
                    func_name="BrowserShellApi.import_selection",
                )
                return {"ok": False, "message": "Unable to read selection."}
        if not selection_text and self._last_selection:
            if not current_url or current_url == self._last_url:
                selection_text = self._last_selection
                if not current_url:
                    current_url = self._last_url
        if not selection_text:
            if not self._content_window and selection is None:
                return {"ok": False, "message": "Browser window not ready."}
            return {"ok": False, "message": "Selection empty."}
        self._last_selection = selection_text
        if current_url:
            self._last_url = current_url
        log_info(
            f"Selection imported from {current_url or 'unknown URL'}: {selection_text}",
            func_name="BrowserShellApi.import_selection",
        )
        if not self.selection_output:
            return {"ok": False, "message": "No output path configured."}
        payload = {
            "selection": selection_text,
            "url": current_url,
            "received_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
        try:
            Path(self.selection_output).write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            log_info(
                f"Unable to persist selection: {exc}",
                func_name="BrowserShellApi.import_selection",
            )
            return {"ok": False, "message": "Unable to save selection."}
        return {"ok": True, "message": "Selection sent."}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch a pywebview browser window")
    parser.add_argument("url", help="URL to open")
    parser.add_argument("--title", default="Image Browser", help="Window title")
    parser.add_argument("--width", type=int, default=1100, help="Window width")
    parser.add_argument("--height", type=int, default=760, help="Window height")
    parser.add_argument("--min-width", type=int, default=900, help="Minimum window width")
    parser.add_argument("--min-height", type=int, default=620, help="Minimum window height")
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Inject the browser shell overlay into the page",
    )
    parser.add_argument(
        "--selection-output",
        help="Optional file path to write the selected text payload",
    )
    return parser.parse_args()


def _attach_content_helpers(window: object) -> None:
    try:
        window.evaluate_js(_CONTENT_SHELL_JS)
    except Exception as exc:
        log_info(
            f"Unable to inject content helpers: {exc}",
            func_name="_attach_content_helpers",
        )


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _qt_available() -> bool:
    return any(
        _module_available(module_name)
        for module_name in ("PyQt6", "PySide6", "PyQt5", "PySide2")
    )


def _cef_available() -> bool:
    return _module_available("cefpython3")


def _edgechromium_available() -> bool:
    return _module_available("clr")


def _webkit_available() -> bool:
    return _module_available("objc") or _module_available("AppKit")


def select_gui() -> str | None:
    if sys.platform.startswith("win"):
        preferred_guis = [("edgechromium", _edgechromium_available)]
    elif sys.platform == "darwin":
        preferred_guis = [("webkit", _webkit_available)]
    else:
        preferred_guis = [
            ("cef", _cef_available),
            ("qt", _qt_available),
        ]

    for gui_name, available in preferred_guis:
        if available():
            return gui_name

    modern_backends = (
        _edgechromium_available(),
        _webkit_available(),
        _cef_available(),
        _qt_available(),
    )
    if any(modern_backends):
        return None

    # TK is a safe fallback but has limited clipboard and context menu support.
    return "tk"


def _default_storage_path() -> str:
    if sys.platform.startswith("win"):
        base_dir = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base_dir:
            return str(Path(base_dir) / "GMCampaignDesigner" / "webview")
        return str(Path.home() / "AppData" / "Local" / "GMCampaignDesigner" / "webview")
    if sys.platform == "darwin":
        return str(
            Path.home()
            / "Library"
            / "Application Support"
            / "GMCampaignDesigner"
            / "webview"
        )
    base_dir = os.environ.get("XDG_STATE_HOME") or os.environ.get("XDG_DATA_HOME")
    if base_dir:
        return str(Path(base_dir) / "gmcampaigndesigner" / "webview")
    return str(Path.home() / ".local" / "share" / "gmcampaigndesigner" / "webview")


def main() -> None:
    args = parse_args()
    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
    api = BrowserShellApi(selection_output=args.selection_output, target_url=args.url)
    if args.shell:
        content_window = webview.create_window(
            args.title,
            args.url,
            width=args.width,
            height=args.height,
            min_size=(args.min_width, args.min_height),
            resizable=True,
            js_api=api,
        )
        api._content_window = content_window
        content_window.events.loaded += lambda: _attach_content_helpers(content_window)
    else:
        webview.create_window(
            args.title,
            args.url,
            width=args.width,
            height=args.height,
            min_size=(args.min_width, args.min_height),
            resizable=True,
            js_api=api,
        )
    webview.start(
        gui=select_gui(),
        debug=True,
        private_mode=False,
        storage_path=_default_storage_path(),
    )


if __name__ == "__main__":
    main()
