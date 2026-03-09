from dataclasses import dataclass

from ai_dev_team import feature_lab
from ai_dev_team.reporting import build_final_report


@dataclass
class _FakeScore:
    approved: bool
    score: int
    reasons: list[str]


@dataclass
class _FakeTests:
    ok: bool
    command: str
    return_code: int


def test_build_final_report_forces_failed_status_when_tests_fail():
    report = build_final_report(
        proposal={"title": "x"},
        review={"approved": True, "score": 95, "reasons": ["good"]},
        tests={"ok": False, "command": "pytest", "return_code": 1},
        changed_files=["a.py"],
    )

    assert report["proposal_review"]["score"] == 95
    assert report["execution"]["status"] == "failed"
    assert report["execution"]["tests"]["ok"] is False


def test_run_feature_lab_uses_normalized_execution_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(feature_lab, "analyze_repository", lambda root: object())
    monkeypatch.setattr(feature_lab.ContextBuilder, "build", lambda self, summary: "ctx")
    monkeypatch.setattr(
        feature_lab.FeatureAgent,
        "propose",
        lambda self, context: type(
            "Proposal",
            (),
            {
                "__dict__": {
                    "title": "t",
                    "rationale": "r",
                    "target_files": ["f.py"],
                    "acceptance_criteria": ["c1", "c2", "c3"],
                }
            },
        )(),
    )
    monkeypatch.setattr(feature_lab.FeatureScorer, "evaluate", lambda self, p: _FakeScore(True, 80, ["ok"]))
    monkeypatch.setattr(feature_lab.PlannerAgent, "plan", lambda self, p: [])
    monkeypatch.setattr(feature_lab.CoderAgent, "implement", lambda self, plan, root: ["x.py"])
    monkeypatch.setattr(feature_lab.TestAgent, "run", lambda self, root: _FakeTests(False, "pytest", 1))

    report = feature_lab.run_feature_lab(tmp_path)

    assert "proposal_review" in report
    assert "execution" in report
    assert "score" not in report
    assert "status" not in report
    assert report["execution"]["status"] == "failed"
    assert report["execution"]["changed_files"] == ["x.py"]


def test_build_final_report_normalizes_windows_style_changed_file_paths():
    report = build_final_report(
        proposal={"title": "x"},
        review={"approved": True, "score": 95, "reasons": ["good"]},
        changed_files=["src\\module\\file.py", "tests\\test_file.py"],
    )

    assert report["execution"]["changed_files"] == ["src/module/file.py", "tests/test_file.py"]
