from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RepoSummary:
    root: Path
    python_files: list[Path]
    test_files: list[Path]
    ui_files: list[Path]
    docs_files: list[Path]

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "python_count": len(self.python_files),
            "test_count": len(self.test_files),
            "ui_count": len(self.ui_files),
            "docs_count": len(self.docs_files),
            "top_modules": self.top_modules(),
        }

    def top_modules(self, limit: int = 8) -> list[str]:
        counts: dict[str, int] = {}
        for path in self.python_files:
            key = path.relative_to(self.root).parts[0]
            counts[key] = counts.get(key, 0) + 1
        return [k for k, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]]


def analyze_repository(root: str | Path = ".") -> RepoSummary:
    repo = Path(root).resolve()
    python_files = sorted(p for p in repo.glob("**/*.py") if p.is_file())
    test_files = [p for p in python_files if "tests" in p.parts or p.name.startswith("test_")]
    ui_files = [p for p in python_files if any(tag in p.parts for tag in ("ui", "web"))]
    docs_files = sorted({*repo.glob("README*"), *repo.glob("docs/**/*.md"), *repo.glob("docs/**/*.html")})
    docs_files = [p for p in docs_files if p.is_file()]
    return RepoSummary(repo, python_files, test_files, ui_files, docs_files)
