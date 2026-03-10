from modules.auto_improve.orchestrator import AutoImproveOrchestrator
from modules.auto_improve.settings import AutoImproveSettings


class DummyRunner:
    pass


def test_dry_run_execution(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "modules.auto_improve.orchestrator.AutoImproveSettings.load",
        classmethod(lambda cls: AutoImproveSettings(dry_run=True)),
    )
    orchestrator = AutoImproveOrchestrator(workdir=tmp_path)
    proposal = orchestrator.list_proposals(limit=1)[0]

    report = orchestrator.execute(proposal)

    assert report.success is True
    assert any("Dry-run mode" in step for step in report.steps)
