from __future__ import annotations

import json
import os
import platform
import subprocess
import tempfile
from typing import Mapping, Sequence

import requests

from modules.ai.base_client import BaseAIClient
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

class LocalAIClient(BaseAIClient):
    """
    Minimal OpenAI-compatible chat client for local models (e.g., gpt-oss,
    LM Studio, Ollama OpenAI adapter, text-gen webui proxy).

    Reads configuration from [AI] in config/config.ini:
      - base_url: server base (e.g., http://localhost:8080)
      - api_key: optional token if your server requires it
      - model:   model name/id to request
      - temperature: default generation temperature (float)
      - max_tokens:  optional default max tokens (int)
      - use_powershell: if true on Windows, call via PowerShell
                        Invoke-WebRequest (default true on Windows)
    """

    def __init__(self):
        # Default to local webserver compatible with /api/generate
        self.base_url = (ConfigHelper.get("AI", "base_url", fallback="http://127.0.0.1:11434") or "").rstrip("/")
        self.api_key = ConfigHelper.get("AI", "api_key", fallback=None)
        self.model = ConfigHelper.get("AI", "model", fallback="gpt-oss:20b")
        # Be resilient to malformed values in config
        try:
            self.temperature = float(ConfigHelper.get("AI", "temperature", fallback="0.7"))
        except Exception:
            self.temperature = 0.7
        try:
            max_tokens_val = ConfigHelper.get("AI", "max_tokens", fallback="0")
            self.max_tokens = int(max_tokens_val) if max_tokens_val else 0
        except Exception:
            self.max_tokens = 0
        # Prefer PowerShell transport on Windows unless disabled in config
        ps_default = "true" if platform.system() == "Windows" else "false"
        self.use_powershell = str(
            ConfigHelper.get("AI", "use_powershell", fallback=ps_default)
        ).strip().lower() in ("1", "true", "yes", "on")

    @staticmethod
    def _parse_json_safe(s: str):
        """Parse JSON from a string that may contain extra leading/trailing text."""

        if s is None:
            raise RuntimeError("Empty response")
        s = s if isinstance(s, str) else str(s)
        s = s.strip()
        if not s:
            raise RuntimeError("Empty response")

        # Fast path: the entire string is valid JSON
        try:
            return json.loads(s)
        except Exception:
            pass

        # Some local AI servers (e.g. Ollama) return newline-delimited JSON
        # fragments even when `stream` is false. Stitch them together so the
        # caller receives the full response text instead of the first chunk.
        json_lines = []
        for line in s.splitlines():
            line = line.strip()
            if not line or line[0] not in "[{":
                continue
            try:
                json_lines.append(json.loads(line))
            except Exception:
                continue
        if json_lines:
            if len(json_lines) == 1:
                return json_lines[0]
            aggregated = {}
            responses = []
            for item in json_lines:
                if not isinstance(item, dict):
                    continue
                text = item.get("response")
                if isinstance(text, str):
                    responses.append(text)
                for key, value in item.items():
                    if key == "response":
                        continue
                    aggregated[key] = value
            if responses:
                aggregated["response"] = "".join(responses)
                return aggregated or {"response": "".join(responses)}
            # No response fragments found, return the last JSON object
            return json_lines[-1]

        # Fall back to locating the first JSON object within the payload
        from json import JSONDecoder

        decoder = JSONDecoder()
        index = 0
        length = len(s)
        while index < length and s[index] not in "{[":
            index += 1
        if index >= length:
            table_data = LocalAIClient._parse_markdown_table(s)
            if table_data is not None:
                return table_data
            raise RuntimeError("No JSON object found in response")
        try:
            obj, _ = decoder.raw_decode(s, idx=index)
            return obj
        except Exception:
            for line in s.splitlines():
                line = line.strip()
                if not line or line[0] not in "{[":
                    continue
                try:
                    return json.loads(line)
                except Exception:
                    continue

            table_data = LocalAIClient._parse_markdown_table(s)
            if table_data is not None:
                return table_data

            raise RuntimeError("No JSON object found in response")

    @staticmethod
    def _parse_markdown_table(text: str):
        """Parse the first markdown table found in text into a list of dicts."""

        if not isinstance(text, str):
            return None

        lines = text.splitlines()
        block = []

        def flush_block():
            nonlocal block
            if not block:
                return None
            header_line = block[0]
            header_line = header_line.strip()
            if not header_line:
                block = []
                return None
            stripped = header_line.lstrip()
            if stripped.startswith("#"):
                stripped = stripped.lstrip("#").strip()
            if not stripped.startswith("|"):
                block = []
                return None
            header_parts = [part.strip() for part in stripped.strip("|").split("|")]
            header_parts = [part for part in header_parts if part]
            if len(header_parts) < 2:
                block = []
                return None
            rows = []
            for row_line in block[1:]:
                stripped = row_line.strip()
                if not stripped:
                    continue
                content = stripped.strip("|")
                if not content:
                    continue
                parts = [part.strip() for part in content.split("|")]
                if len(parts) != len(header_parts):
                    continue
                # Skip separator rows like |---|---|
                joined = "".join(parts).replace("-", "").replace(":", "").strip()
                if not joined:
                    continue
                row = {header_parts[i]: parts[i] for i in range(len(header_parts))}
                rows.append(row)
            block = []
            return rows or None

        for line in lines:
            if "|" in line:
                block.append(line)
            else:
                result = flush_block()
                if result:
                    return result
        result = flush_block()
        if result:
            return result
        return None

    def _powershell_generate(self, url, payload, headers):
        """POST to url using PowerShell Invoke-WebRequest.

        Returns parsed JSON dict.
        """
        # Build headers hashtable
        header_parts = ["\"Content-Type\" = \"application/json\""]
        if headers and isinstance(headers, dict) and headers.get("Authorization"):
            header_parts.append(f"\"Authorization\" = \"{headers['Authorization']}\"")
        headers_ps = "@{ " + "; ".join(header_parts) + " }"

        json_text = json.dumps(payload, ensure_ascii=False)
        script = (
            "${ErrorActionPreference} = 'Stop'\n"
            "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false\n"
            "$json = @'\n" + json_text + "\n'@\n"
            f"$resp = Invoke-WebRequest -Uri '{url}' -Method Post -Headers {headers_ps} -Body $json\n"
            "$resp.Content\n"
        )

        # Write with UTF-8 BOM so Windows PowerShell 5.1 reads it as UTF-8
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ps1", mode="w", encoding="utf-8-sig") as tf:
            tf.write(script)
            ps1 = tf.name
        try:
            run = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1],
                capture_output=True, check=True
            )
        except subprocess.CalledProcessError as e:
            # Decode stderr/stdout robustly for diagnostics
            def _dec(b):
                for enc in ("utf-8", "utf-16-le", "utf-16", "cp65001", "cp1252", "latin-1"):
                    try:
                        return (b or b"").decode(enc)
                    except Exception:
                        continue
                return (b or b"").decode("latin-1", errors="replace")
            err = _dec(e.stderr) if isinstance(e.stderr, (bytes, bytearray)) else str(e.stderr)
            out = _dec(e.stdout) if isinstance(e.stdout, (bytes, bytearray)) else str(e.stdout)
            raise RuntimeError(f"PowerShell failed: {err or out}")
        finally:
            try:
                os.remove(ps1)
            except Exception:
                pass

        # Decode stdout robustly
        def _dec(b):
            for enc in ("utf-8", "utf-16-le", "utf-16", "cp65001", "cp1252", "latin-1"):
                try:
                    return (b or b"").decode(enc)
                except Exception:
                    continue
            return (b or b"").decode("latin-1", errors="replace")
        out = _dec(run.stdout)
        if not out or not out.strip():
            raise RuntimeError("PowerShell returned empty content")

        try:
            return self._parse_json_safe(out)
        except Exception as e:
            raise RuntimeError(f"Could not parse PowerShell JSON: {e}. Raw: {out[:500]}")

    def chat(
        self,
        messages: Sequence[Mapping[str, str]] | str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int = 600,
    ):
        """
        Send a chat completion request and return the assistant's text.

        messages: list[{role, content}] per OpenAI API
        """
        # Build a single prompt string from chat-style messages
        prompt_text = BaseAIClient.format_messages(messages)

        # Target Ollama/text-gen style endpoint as per template
        # e.g. http://127.0.0.1:11434/api/generate
        generate_path = "/api/generate"
        url = f"{self.base_url}{generate_path}"

        payload = {
            "model": model or self.model,
            "prompt": prompt_text,
            "stream": False,
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        data = None
        # Optionally use PowerShell to make the request (matches user template)
        if self.use_powershell and platform.system() == "Windows":
            try:
                data = self._powershell_generate(url, payload, headers)
            except Exception:
                # Fallback to requests if PowerShell path fails
                data = None
        if data is None:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = self._parse_json_safe(resp.text)

        # Prefer Ollama/text-gen style response key
        if isinstance(data, dict):
            if "response" in data and isinstance(data["response"], str):
                return data["response"].strip()
            # OpenAI-compatible fallbacks
            if "choices" in data and data["choices"]:
                choice = data["choices"][0]
                if isinstance(choice, dict):
                    if "message" in choice and isinstance(choice["message"], dict):
                        content = choice["message"].get("content")
                        if isinstance(content, str):
                            return content.strip()
                    if "text" in choice and isinstance(choice["text"], str):
                        return choice["text"].strip()

        # If we reach here, return raw string if possible, else raise
        if isinstance(data, str):
            return data.strip()
        raise ValueError("Unexpected AI response format")
