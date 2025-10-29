import sys
import types

import pytest

if "winsound" not in sys.modules:
    winsound_stub = types.ModuleType("winsound")
    winsound_stub.SND_FILENAME = 0
    winsound_stub.SND_ASYNC = 0
    winsound_stub.SND_PURGE = 0

    def _noop(*_args, **_kwargs):
        return None

    winsound_stub.PlaySound = _noop
    sys.modules["winsound"] = winsound_stub

from modules.generic.cross_campaign_asset_service import (
    CampaignDatabase,
    export_bundle,
)


def test_export_bundle_raises_when_database_missing(tmp_path):
    destination = tmp_path / "export.zip"
    source_campaign = CampaignDatabase(
        name="MissingDB",
        root=tmp_path,
        db_path=tmp_path / "does_not_exist.db",
    )

    with pytest.raises(FileNotFoundError):
        export_bundle(
            destination=destination,
            source_campaign=source_campaign,
            selected_records={},
            include_database=True,
        )

    assert not destination.exists()
