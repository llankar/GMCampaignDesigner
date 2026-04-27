import configparser

from modules.ui.ambiance.settings import (
    AmbianceSettings,
    load_ambiance_settings,
    save_ambiance_settings,
    update_ambiance_settings,
)


def test_save_and_load_ambiance_settings(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.ini"
    monkeypatch.setattr(
        "modules.ui.ambiance.settings.ConfigHelper.get_campaign_settings_path",
        staticmethod(lambda: str(settings_path)),
    )
    monkeypatch.setattr(
        "modules.ui.ambiance.settings.ConfigHelper.load_campaign_config",
        staticmethod(lambda: configparser.ConfigParser()),
    )

    save_ambiance_settings(
        AmbianceSettings(
            enabled=True,
            playlist_paths=("a.json", "/tmp/media"),
            default_duration_sec=12.5,
            transition="cut",
            shuffle=True,
            loop=False,
            target_monitor_index=2,
        )
    )

    cfg = configparser.ConfigParser()
    cfg.read(settings_path, encoding="utf-8")
    monkeypatch.setattr(
        "modules.ui.ambiance.settings.ConfigHelper.load_campaign_config",
        staticmethod(lambda: cfg),
    )

    loaded = load_ambiance_settings()
    assert loaded.enabled is True
    assert loaded.playlist_paths == ("a.json", "/tmp/media")
    assert loaded.default_duration_sec == 12.5
    assert loaded.transition == "cut"
    assert loaded.shuffle is True
    assert loaded.loop is False
    assert loaded.target_monitor_index == 2


def test_update_ambiance_settings_partial_update(tmp_path, monkeypatch):
    settings_path = tmp_path / "settings.ini"
    monkeypatch.setattr(
        "modules.ui.ambiance.settings.ConfigHelper.get_campaign_settings_path",
        staticmethod(lambda: str(settings_path)),
    )

    cfg = configparser.ConfigParser()
    monkeypatch.setattr(
        "modules.ui.ambiance.settings.ConfigHelper.load_campaign_config",
        staticmethod(lambda: cfg),
    )
    save_ambiance_settings(AmbianceSettings(enabled=False, loop=True))

    cfg = configparser.ConfigParser()
    cfg.read(settings_path, encoding="utf-8")
    monkeypatch.setattr(
        "modules.ui.ambiance.settings.ConfigHelper.load_campaign_config",
        staticmethod(lambda: cfg),
    )
    updated = update_ambiance_settings(enabled=True, playlist_paths=["x.json"])

    assert updated.enabled is True
    assert updated.playlist_paths == ("x.json",)
