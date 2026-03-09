"""Context builder transforms repository scan output into agent-ready text."""

from __future__ import annotations

from textwrap import dedent

try:
    from .repo_analyzer import RepoSummary
except ImportError:
    from repo_analyzer import RepoSummary


class ContextBuilder:
    """Build compact context blocks for proposal, planning, and coding."""

    def build(self, summary: RepoSummary) -> str:
        top_py = [str(p.relative_to(summary.root)) for p in summary.python_files[:12]]
        top_tests = [str(p.relative_to(summary.root)) for p in summary.test_files[:8]]
        payload = dedent(
            f"""
            Repository root: {summary.root}
            Python files: {len(summary.python_files)}
            Tests: {len(summary.test_files)}
            UI-related Python files: {len(summary.ui_files)}
            Documentation files: {len(summary.docs_files)}
            Top modules: {', '.join(summary.top_modules())}

            Sample Python files:
            - """
        ).strip()
        payload += "\n- ".join([""] + top_py)
        if top_tests:
            payload += "\n\nSample test files:\n- " + "\n- ".join(top_tests)
        return payload
