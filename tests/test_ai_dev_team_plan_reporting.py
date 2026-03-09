from ai_dev_team.reporting import build_final_report


PLAN = [
    {"id": 1, "description": "Inspect target files and current architecture constraints."},
    {"id": 2, "description": "Implement minimal code changes required for the proposal."},
    {"id": 3, "description": "Add or update pytest coverage for the new behavior."},
    {"id": 4, "description": "Run pytest and collect output."},
    {"id": 5, "description": "Prepare branch and commit metadata for PR automation."},
]


def test_plan_states_fail_implementation_and_block_pr_step_when_targets_not_changed():
    report = build_final_report(
        proposal={"title": "x", "target_files": ["src/target.py"]},
        review={"approved": True, "score": 90, "reasons": ["ok"]},
        plan=PLAN,
        changed_files=["src/other.py"],
        tests={"ok": True, "command": "pytest", "return_code": 0},
    )

    states = {step["id"]: step["state"] for step in report["plan"]}
    assert states[2] == "failed"
    assert states[4] == "completed"
    assert states[5] == "failed"
    assert report["execution"]["status"] == "failed"


def test_plan_states_fail_test_step_on_non_zero_pytest_exit_and_block_pr_step():
    report = build_final_report(
        proposal={"title": "x", "target_files": ["src/target.py"]},
        review={"approved": True, "score": 90, "reasons": ["ok"]},
        plan=PLAN,
        changed_files=["src/target.py"],
        tests={"ok": False, "command": "pytest -q", "return_code": 2},
    )

    states = {step["id"]: step["state"] for step in report["plan"]}
    assert states[2] == "completed"
    assert states[4] == "failed"
    assert states[5] == "failed"


def test_plan_states_complete_for_successful_implementation_and_tests():
    report = build_final_report(
        proposal={"title": "x", "target_files": ["src/target.py"]},
        review={"approved": True, "score": 90, "reasons": ["ok"]},
        plan=PLAN,
        changed_files=["src/target.py"],
        tests={"ok": True, "command": "pytest", "return_code": 0},
    )

    assert {step["state"] for step in report["plan"]} == {"completed"}

def test_plan_states_pending_when_proposal_not_approved():
    report = build_final_report(
        proposal={"title": "x", "target_files": ["src/target.py"]},
        review={"approved": False, "score": 10, "reasons": ["no"]},
        plan=PLAN,
        changed_files=[],
        tests={"ok": False, "command": "pytest", "return_code": 1},
    )

    assert {step["state"] for step in report["plan"]} == {"pending"}


def test_plan_states_fail_when_only_implementation_artifact_is_changed():
    report = build_final_report(
        proposal={"title": "x", "target_files": ["ai_dev_team/feature_lab.py"]},
        review={"approved": True, "score": 90, "reasons": ["ok"]},
        plan=PLAN,
        changed_files=["ai_dev_team/last_run/implementation.md"],
        tests={"ok": True, "command": "pytest", "return_code": 0},
    )

    states = {step["id"]: step["state"] for step in report["plan"]}
    assert states[2] == "failed"
    assert states[5] == "failed"
