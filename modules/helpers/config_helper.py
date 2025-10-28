import configparser
import os
from pathlib import Path
from typing import Union


class ConfigHelper:
    _instance = None
    _config = None
    _config_mtime = None
    _campaign_config = None
    _campaign_mtime = None
    _config_path: Path = Path("config/config.ini")

    @classmethod
    def load_config(cls, file_path: Union[str, os.PathLike] = "config/config.ini"):
        """Load the configuration from ``file_path``.

        The file is read only when it's not cached or when the file has
        changed on disk since the last load. This allows updating the
        configuration without restarting the application.
        """
        path = Path(file_path)
        cls._config_path = path
        mtime = os.path.getmtime(path) if path.exists() else None

        if cls._config is None or mtime != cls._config_mtime:
            cls._config = configparser.ConfigParser()
            if mtime is not None:
                cls._config.read(str(path), encoding="utf-8")
                cls._config_mtime = mtime
            else:
                print(f"Warning: config file '{path}' not found.")
                cls._config_mtime = None

        return cls._config

    @classmethod
    def get(cls, section, key, fallback=None):
        cls.load_config()
        try:
            return cls._config.get(section, key, fallback=fallback)
        except Exception as e:
            print(f"Config error: [{section}] {key} â€” {e}")
            return fallback

    @classmethod
    def getboolean(cls, section, key, fallback=False):
        cls.load_config()
        try:
            return cls._config.getboolean(section, key, fallback=fallback)
        except Exception as e:
            print(f"Config error: [{section}] {key} â€” {e}")
            return fallback

    @classmethod
    def set(cls, section, key, value, file_path: Union[str, os.PathLike, None] = None):
        if file_path is None:
            config_path = cls.get_config_path()
        else:
            config_path = Path(file_path)

        config = configparser.ConfigParser()
        if config_path.exists():
            config.read(str(config_path), encoding="utf-8")

        if not config.has_section(section):
            config.add_section(section)

        config.set(section, key, str(value))

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as configfile:
            config.write(configfile)

        # Refresh cached configuration so subsequent reads observe the new value.
        cls.load_config(str(config_path))

    @classmethod
    def get_config_path(cls) -> Path:
        if not isinstance(cls._config_path, Path):
            cls._config_path = Path("config/config.ini")
        return cls._config_path

    @classmethod
    def get_campaign_dir(cls):
        """Return the directory containing the configured database file."""
        db_path = cls.get("Database", "path", fallback="default_campaign.db")
        return os.path.abspath(os.path.dirname(db_path))

    @classmethod
    def get_campaign_settings_path(cls):
        """Path to campaign-local settings file stored next to the DB."""
        return os.path.join(cls.get_campaign_dir(), "settings.ini")

    @classmethod
    def load_campaign_config(cls):
        """Load campaign-local settings.ini, cached by mtime similar to load_config."""
        path = cls.get_campaign_settings_path()
        mtime = os.path.getmtime(path) if os.path.exists(path) else None
        if cls._campaign_config is None or mtime != cls._campaign_mtime:
            cfg = configparser.ConfigParser()
            if mtime is not None:
                cfg.read(path)
                cls._campaign_mtime = mtime
            else:
                cls._campaign_mtime = None
            cls._campaign_config = cfg
        return cls._campaign_config


# Late import to avoid circular dependency with logging_helper
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)
