from pathlib import Path

from ai_dev_team import feature_lab
from ai_dev_team.repo_analyzer import analyze_repository, architecture_summary_text


def test_analyze_repository_reports_python_files():
    summary = analyze_repository(Path(__file__).resolve().parents[1])
    assert summary.python_files
    assert summary.to_dict()["python_count"] >= len(summary.test_files)


def test_architecture_summary_text_contains_expected_sections(tmp_path):
    (tmp_path / "module_a").mkdir()
    (tmp_path / "module_a" / "app.py").write_text("print('ok')\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_ok():\n    assert True\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n")

    summary_text = architecture_summary_text(tmp_path)

    assert "Repository:" in summary_text
    assert "Python files: 2" in summary_text
    assert "Test files: 1" in summary_text
    assert "Docs files: 1" in summary_text
    assert "Top modules:" in summary_text


def test_feature_lab_cli_architecture_summary_exits_early(monkeypatch, capsys, tmp_path):
    (tmp_path / "sample.py").write_text("print('x')\n")
    monkeypatch.setattr(feature_lab, "run_feature_lab", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run")))
    monkeypatch.setattr("sys.argv", ["feature_lab.py", "--workspace", str(tmp_path), "--architecture-summary"])

    feature_lab.main()

    out = capsys.readouterr().out
    assert "Repository:" in out
    assert "Python files: 1" in out
