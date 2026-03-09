from pathlib import Path

from ai_dev_team.cli.architecture_summary import build_architecture_summary


def test_build_architecture_summary_reports_expected_counts(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "logic.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_logic.py").write_text("def test_ok():\n    assert True\n")

    summary = build_architecture_summary(Path(tmp_path))

    assert "Repository:" in summary
    assert "Python files: 2" in summary
    assert "Test files: 1" in summary
