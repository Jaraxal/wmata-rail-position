import logging
import os
import tomllib
from pathlib import Path
from typing import Any

from logger import configure_logging

# Configure logging at module level
configure_logging()
logger = logging.getLogger()


class ConfigError(Exception):
    """Custom exception for configuration-related errors."""

    pass


class ConfigLoader:
    """Handles loading and validating configuration settings and secrets."""

    def __init__(
        self,
        settings_file: str = os.getenv("CONFIG_SETTINGS_FILE", "./config/settings.toml"),
        secrets_file: str = os.getenv("CONFIG_SECRETS_FILE", "./config/.secrets.toml"),
    ):
        self.settings_file = Path(settings_file)
        self.secrets_file = Path(secrets_file)
        self.settings: dict[str, Any] = {}
        self.secrets: dict[str, Any] = {}

    def load_config(self) -> None:
        """Load settings and secrets from TOML files."""
        if not self.settings_file.exists():
            raise ConfigError(f"Settings file not found: {self.settings_file}")

        if not self.secrets_file.exists():
            raise ConfigError(f"Secrets file not found: {self.secrets_file}")

        # Load configurations
        with self.settings_file.open(mode="rb") as fp:
            self.settings = tomllib.load(fp)

        with self.secrets_file.open(mode="rb") as fp:
            self.secrets = tomllib.load(fp)

        # Load environment variables

        #self.settings["DEBUG"] = os.getenv("DEBUG", "FALSE")
        #self.settings["MODE"] = os.getenv("MODE", "STABLE")

        print(self.settings)
        print(self.secrets)
        logger.info("Loaded settings.")
        logger.info("Loaded secrets.")

    def validate_config(self, required_settings: list[str], required_secrets: list[str]) -> None:
        """
        Validate that all required settings and secrets are present.

        Args:
            required_settings (List[str]): Keys that must be present in the settings file.
            required_secrets (List[str]): Keys that must be present in the secrets file.

        Raises:
            ConfigError: If any required setting or secret is missing.
        """
        missing_settings = [key for key in required_settings if key not in self.settings]
        missing_secrets = [key for key in required_secrets if key not in self.secrets]

        if missing_settings:
            raise ConfigError(f"Missing required settings: {', '.join(missing_settings)}")

        if missing_secrets:
            raise ConfigError(f"Missing required secrets: {', '.join(missing_secrets)}")

    def get(self, key: str, config_type: str = "settings", default: Any = None) -> Any:
        """
        Retrieve a configuration value.

        Args:
            key (str): The key to retrieve.
            config_type (str): "settings" or "secrets".
            default (Any): Default value if the key is not found.

        Returns:
            Any: The configuration value.
        """
        config = self.settings if config_type == "settings" else self.secrets
        return config.get(key, default)
