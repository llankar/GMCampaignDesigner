import configparser
import os

class ConfigHelper:
    _instance = None
    _config = None
    _config_mtime = None
    _campaign_config = None
    _campaign_mtime = None

    @classmethod
    def load_config(cls, file_path="config/config.ini"):
        """Load the configuration from ``file_path``.

        The file is read only when it's not cached or when the file has
        changed on disk since the last load. This allows updating the
        configuration without restarting the application.
        """
        mtime = os.path.getmtime(file_path) if os.path.exists(file_path) else None

        if cls._config is None or mtime != cls._config_mtime:
            cls._config = configparser.ConfigParser()
            if mtime is not None:
                cls._config.read(file_path)
                cls._config_mtime = mtime
            else:
                print(f"Warning: config file '{file_path}' not found.")
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

    def set(section, key, value, file_path="config/config.ini"):
        config = configparser.ConfigParser()
        if os.path.exists(file_path):
            config.read(file_path)

        if not config.has_section(section):
            config.add_section(section)

        config.set(section, key, str(value))

        with open(file_path, "w", encoding="utf-8") as configfile:
            config.write(configfile)

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

