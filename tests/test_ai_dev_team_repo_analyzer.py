from pathlib import Path

from ai_dev_team.repo_analyzer import analyze_repository


def test_analyze_repository_reports_python_files():
    summary = analyze_repository(Path(__file__).resolve().parents[1])
    assert summary.python_files
    assert summary.to_dict()["python_count"] >= len(summary.test_files)
