from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
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
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


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
                    dest_file.unlink()
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest_file)


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


if __name__ == "__main__":
    main()
