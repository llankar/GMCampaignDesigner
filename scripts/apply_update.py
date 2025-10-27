from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Sequence, Set, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a staged GMCampaignDesigner update.")
    parser.add_argument("--source", required=True, help="Extracted release payload directory.")
    parser.add_argument("--target", required=True, help="Installation root to overwrite.")
    parser.add_argument("--preserve", action="append", default=[], help="Relative paths to leave untouched.")
    parser.add_argument("--wait-for-pid", type=int, default=0, help="PID to wait on before copying.")
    parser.add_argument("--wait-timeout", type=int, default=900, help="Seconds to wait for the PID to exit.")
    parser.add_argument("--restart-target", help="Executable to relaunch after copying.")
    parser.add_argument("--cleanup-root", help="Temporary directory to delete once finished.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source).resolve()
    target = Path(args.target).resolve()
    if not source.exists():
        raise SystemExit(f"Update payload not found: {source}")
    if not target.exists():
        raise SystemExit(f"Install target not found: {target}")

    preserved = {_normalize_preserve_path(value) for value in args.preserve}
    if args.wait_for_pid:
        _wait_for_pid(args.wait_for_pid, args.wait_timeout)

    print(f"Applying update from {source} to {target}")
    _copy_release_tree(source, target, preserved)

    if args.cleanup_root:
        cleanup_root = Path(args.cleanup_root)
        shutil.rmtree(cleanup_root, ignore_errors=True)

    if args.restart_target:
        try:
            subprocess.Popen([args.restart_target], close_fds=os.name != "nt")
        except Exception as exc:
            print(f"Warning: unable to relaunch application: {exc}", file=sys.stderr)
    print("Update applied successfully.")


def _wait_for_pid(pid: int, timeout: int) -> None:
    deadline = time.time() + max(timeout, 0)
    while time.time() < deadline:
        if not _is_pid_alive(pid):
            return
        time.sleep(0.5)
    raise SystemExit(f"Process {pid} did not exit within {timeout} seconds.")


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False

    if os.name == "nt":
        win_status = _is_pid_alive_windows(pid)
        if win_status is not None:
            return win_status

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 5:
            return True
        return True
    except OSError:
        return False
    return True


def _is_pid_alive_windows(pid: int) -> bool | None:
    """Return ``True`` if ``pid`` is running on Windows, ``False`` if it exited."""

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return None

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SYNCHRONIZE = 0x00100000
    WAIT_OBJECT_0 = 0x00000000
    WAIT_TIMEOUT = 0x00000102

    access = SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION

    ctypes.set_last_error(0)
    handle = kernel32.OpenProcess(access, False, wintypes.DWORD(pid))
    if not handle and ctypes.get_last_error() == 5:
        return True

    if not handle:
        ctypes.set_last_error(0)
        handle = kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_INFORMATION, False, wintypes.DWORD(pid))
        if not handle:
            last_error = ctypes.get_last_error()
            if last_error == 5:
                return True
            if last_error in (0, 87):
                return False
            return None

    try:
        result = kernel32.WaitForSingleObject(handle, 0)
        if result == WAIT_TIMEOUT:
            return True
        if result == WAIT_OBJECT_0:
            return False
        return None
    finally:
        kernel32.CloseHandle(handle)


def _copy_release_tree(source: Path, target: Path, preserved: Set[Tuple[str, ...]]) -> None:
    for root, dirs, files in os.walk(source):
        root_path = Path(root)
        rel_root = root_path.relative_to(source)
        rel_root_parts = rel_root.parts
        if _is_preserved(_normalize_parts(rel_root_parts), preserved):
            dirs[:] = []
            continue
        target_root = target / rel_root
        target_root.mkdir(parents=True, exist_ok=True)
        for name in files:
            rel_path = rel_root / name if rel_root_parts else Path(name)
            if _is_preserved(_normalize_parts(rel_path.parts), preserved):
                continue
            src_file = root_path / name
            dest_file = target / rel_path
            if dest_file.exists():
                if dest_file.is_dir():
                    shutil.rmtree(dest_file)
                else:
                    _copy_file_with_replace(src_file, dest_file)
                    continue
            _copy_file_with_replace(src_file, dest_file)


def _copy_file_with_replace(src_file: Path, dest_file: Path) -> None:
    """Copy ``src_file`` to ``dest_file`` replacing the target atomically."""

    dest_file.parent.mkdir(parents=True, exist_ok=True)
    temp_name = dest_file.parent / f".{dest_file.name}.tmp.{uuid.uuid4().hex}"
    shutil.copy2(src_file, temp_name)
    _replace_with_retry(temp_name, dest_file)


def _normalize_preserve_path(value: str) -> Tuple[str, ...]:
    parts = tuple(part for part in Path(value).parts if part not in (".", ""))
    return _normalize_parts(parts)


def _normalize_parts(parts: Sequence[str]) -> Tuple[str, ...]:
    if os.name == "nt":
        return tuple(part.casefold() for part in parts)
    return tuple(parts)


def _is_preserved(rel_parts: Sequence[str], preserved: Set[Tuple[str, ...]]) -> bool:
    for entry in preserved:
        if rel_parts[: len(entry)] == entry:
            return True
    return False


def _replace_with_retry(src: Path, dest: Path, attempts: int = 10, delay: float = 0.5) -> None:
    last_exc: Exception | None = None
    for _ in range(max(1, attempts)):
        try:
            os.replace(src, dest)
            return
        except PermissionError as exc:
            last_exc = exc
            if attempts <= 1:
                break
            time.sleep(max(0, delay))
        except Exception:
            src.unlink(missing_ok=True)
            raise

    src.unlink(missing_ok=True)
    if last_exc is not None:
        raise last_exc
    raise PermissionError(f"Unable to replace {dest}")


if __name__ == "__main__":
    main()
