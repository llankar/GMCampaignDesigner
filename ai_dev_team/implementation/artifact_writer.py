from __future__ import annotations

from pathlib import Path

try:
    from ..repo_analyzer import architecture_summary_text
except ImportError:
    from repo_analyzer import architecture_summary_text


def write_architecture_snapshot(workspace: str | Path = ".") -> Path:
    """Generate a repository architecture snapshot under docs/architecture."""
    root = Path(workspace).resolve()
    out_dir = root / "docs" / "architecture"
    out_dir.mkdir(parents=True, exist_ok=True)

    output = out_dir / "ai_dev_team_summary.md"
    summary = architecture_summary_text(root)
    body = "\n".join([
        "# AI Dev Team Architecture Snapshot",
        "",
        "```text",
        summary,
        "```",
        "",
    ])
    output.write_text(body, encoding="utf-8")
    return output
