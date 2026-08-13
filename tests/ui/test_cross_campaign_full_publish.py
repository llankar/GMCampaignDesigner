"""Unit contracts for the explicit full-campaign synchronization action."""

from pathlib import Path
from types import SimpleNamespace
import sys
import types

if "cryptography.fernet" not in sys.modules:
    cryptography = types.ModuleType("cryptography")
    fernet = types.ModuleType("cryptography.fernet")
    fernet.Fernet = object
    fernet.InvalidToken = ValueError
    cryptography.fernet = fernet
    sys.modules.setdefault("cryptography", cryptography)
    sys.modules.setdefault("cryptography.fernet", fernet)

from modules.generic.campaign_sync.publisher import PublishOutcome
from modules.generic.campaign_sync.auto_publish.models import EventKind, SyncState, WorkerEvent
import modules.generic.cross_campaign_asset_library as library


def _window(*, can_publish=True):
    window = object.__new__(library.CrossCampaignAssetLibraryWindow)
    window.selected_campaign = SimpleNamespace(
        name="Demo", root=Path("/campaign"), db_path=Path("/campaign/demo.db")
    )
    window.gallery_client = SimpleNamespace(can_publish=can_publish)
    window.master = SimpleNamespace()
    window._refresh_online_dialog = lambda: None
    return window


def test_full_publish_requires_campaign_and_credentials(monkeypatch):
    messages = []
    monkeypatch.setattr(library.messagebox, "showwarning", lambda *args, **kwargs: messages.append(args))
    monkeypatch.setattr(library.messagebox, "showerror", lambda *args, **kwargs: messages.append(args))
    window = _window()
    window.selected_campaign = None
    window.publish_full_campaign_to_github()
    assert messages[-1][0] == "No Source"

    window = _window(can_publish=False)
    window.publish_full_campaign_to_github()
    assert messages[-1][0] == "GitHub Token Required"


def test_full_publish_cancellation_does_not_start_background_work(monkeypatch):
    window = _window()
    window.campaign_publisher = SimpleNamespace(
        enable=lambda *_args, **_kwargs: SimpleNamespace(revision=4, published_at="yes")
    )
    called = []
    window._run_progress_task = lambda *args, **kwargs: called.append((args, kwargs))
    monkeypatch.setattr(library.messagebox, "askyesno", lambda *args, **kwargs: False)

    window.publish_full_campaign_to_github()

    assert called == []


def test_full_publish_forwards_flag_and_reports_conflict_and_error(monkeypatch):
    window = _window()
    publish_calls = []
    window.campaign_publisher = SimpleNamespace(
        enable=lambda *_args, **_kwargs: SimpleNamespace(revision=4, published_at="yes"),
        publish=lambda *args, **kwargs: publish_calls.append(kwargs) or SimpleNamespace(
            outcome=PublishOutcome.CONFLICTED,
            revision=5,
            conflict_message="duplicate revision",
        ),
    )
    monkeypatch.setattr(library.messagebox, "askyesno", lambda *args, **kwargs: True)
    warnings = []
    monkeypatch.setattr(library.messagebox, "showwarning", lambda *args, **kwargs: warnings.append(args))

    def run(_title, worker, *_args, on_success, **_kwargs):
        on_success(worker(lambda *_args: None))

    window._run_progress_task = run
    window.publish_full_campaign_to_github()
    assert publish_calls[0]["force_full_checkpoint"] is True
    assert warnings[-1] == ("Publication Conflict", "duplicate revision")

    window.campaign_publisher.publish = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("upload failed"))
    errors = []
    window._run_progress_task = lambda _title, worker, *_args, **_kwargs: errors.append(worker)
    window.publish_full_campaign_to_github()
    try:
        errors[0](lambda *_args: None)
    except RuntimeError as exc:
        assert str(exc) == "upload failed"
    else:
        raise AssertionError("publication error was swallowed")


def test_full_publish_with_coordinator_reports_start_and_completion(monkeypatch):
    window = _window()
    metadata = SimpleNamespace(campaign_id="campaign-1", revision=4, published_at="yes")
    window.campaign_publisher = SimpleNamespace(enable=lambda *_args, **_kwargs: metadata)
    coordinator = SimpleNamespace(mark_dirty=lambda **_kwargs: None, publish_now=lambda _id: True)
    window.master._auto_publish_coordinator = coordinator
    monkeypatch.setattr(library.messagebox, "askyesno", lambda *args, **kwargs: True)
    notices = []
    monkeypatch.setattr(
        library.messagebox, "showinfo", lambda *args, **kwargs: notices.append(args)
    )

    window.publish_full_campaign_to_github()
    assert notices[-1][0] == "Publication Started"

    window.handle_auto_publish_event(
        WorkerEvent(
            "job-1",
            "campaign-1",
            1,
            EventKind.SUCCESS,
            SyncState.SYNCHRONIZED,
            "Revision 5 published",
            terminal=True,
        )
    )
    assert notices[-1] == ("Campaign Published", "Revision 5 published")


def test_full_publish_reports_when_coordinator_rejects_dispatch(monkeypatch):
    window = _window()
    metadata = SimpleNamespace(campaign_id="campaign-1", revision=4, published_at="yes")
    window.campaign_publisher = SimpleNamespace(enable=lambda *_args, **_kwargs: metadata)
    window.master._auto_publish_coordinator = SimpleNamespace(
        mark_dirty=lambda **_kwargs: None, publish_now=lambda _id: False
    )
    monkeypatch.setattr(library.messagebox, "askyesno", lambda *args, **kwargs: True)
    errors = []
    monkeypatch.setattr(
        library.messagebox, "showerror", lambda *args, **kwargs: errors.append(args)
    )

    window.publish_full_campaign_to_github()

    assert errors[-1][0] == "Publication Not Started"
