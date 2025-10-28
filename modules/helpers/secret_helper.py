from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_exception, log_module_import, log_warning

_SECRET_PREFIX = "enc::"
_KEY_ENV_VAR = "GMCD_SECRET_KEY_PATH"
_KEY_FILENAME = ".gmcd_secret.key"

_FERNET: Optional[Fernet] = None
_KEY_PATH: Optional[Path] = None


def _get_key_path() -> Path:
    global _KEY_PATH
    if _KEY_PATH is not None:
        return _KEY_PATH

    env_path = os.environ.get(_KEY_ENV_VAR)
    if env_path:
        candidate = Path(env_path).expanduser()
    else:
        config_path = ConfigHelper.get_config_path()
        candidate = config_path.parent / _KEY_FILENAME

    candidate.parent.mkdir(parents=True, exist_ok=True)
    _KEY_PATH = candidate
    return candidate


def _load_or_create_key() -> bytes:
    key_path = _get_key_path()
    if key_path.exists():
        return key_path.read_bytes()

    key = Fernet.generate_key()
    key_path.write_bytes(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        # Best-effort on platforms that support chmod
        pass
    return key


def _get_fernet() -> Optional[Fernet]:
    global _FERNET
    if _FERNET is not None:
        return _FERNET

    try:
        key = _load_or_create_key()
    except Exception as exc:  # pragma: no cover - defensive logging
        log_exception(
            f"Failed to load encryption key: {exc}",
            func_name="modules.helpers.secret_helper._get_fernet",
        )
        return None

    try:
        _FERNET = Fernet(key)
    except Exception as exc:  # pragma: no cover - defensive logging
        log_exception(
            f"Failed to initialize encryption cipher: {exc}",
            func_name="modules.helpers.secret_helper._get_fernet",
        )
        return None

    return _FERNET


def is_encrypted_secret(value: Optional[str]) -> bool:
    return bool(value and value.startswith(_SECRET_PREFIX))


def encrypt_secret(value: Optional[str]) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""

    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError("Encryption subsystem is unavailable.")

    token = fernet.encrypt(normalized.encode("utf-8"))
    return f"{_SECRET_PREFIX}{token.decode('utf-8')}"


def decrypt_secret(value: Optional[str]) -> str:
    if not value:
        return ""
    value = value.strip()
    if not value:
        return ""

    if not is_encrypted_secret(value):
        return value

    fernet = _get_fernet()
    if fernet is None:
        log_warning(
            "Encryption key unavailable; returning empty secret.",
            func_name="modules.helpers.secret_helper.decrypt_secret",
        )
        return ""

    token = value[len(_SECRET_PREFIX) :].encode("utf-8")
    try:
        decrypted = fernet.decrypt(token)
    except InvalidToken:
        log_warning(
            "Failed to decrypt secret value; ignoring stored secret.",
            func_name="modules.helpers.secret_helper.decrypt_secret",
        )
        return ""
    except Exception as exc:  # pragma: no cover - defensive logging
        log_exception(
            f"Unexpected error while decrypting secret: {exc}",
            func_name="modules.helpers.secret_helper.decrypt_secret",
        )
        return ""

    return decrypted.decode("utf-8")


log_module_import(__name__)
