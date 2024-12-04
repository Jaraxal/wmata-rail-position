import os
import pathlib

import tomllib


def load_toml_file(file_path):
    """
    Load a TOML file and return its contents as a dictionary.

    Args:
        file_path (pathlib.Path): The path to the TOML file.

    Returns:
        dict: The contents of the TOML file.

    Raises:
        FileNotFoundError: If the TOML file does not exist.
        IsADirectoryError: If the provided path is a directory.
        tomllib.TOMLDecodeError: If the file is not a valid TOML.
        PermissionError: If there is a permission issue opening the file.
    """
    try:
        with file_path.open(mode="rb") as fp:
            return tomllib.load(fp)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"TOML file not found at {file_path}: {e}")
    except IsADirectoryError as e:
        raise IsADirectoryError(
            f"Expected a file but got a directory at {file_path}: {e}"
        )
    except tomllib.TOMLDecodeError as e:
        raise tomllib.TOMLDecodeError(f"Failed to parse TOML file at {file_path}: {e}")
    except PermissionError as e:
        raise PermissionError(
            f"Permission denied when accessing file at {file_path}: {e}"
        )


def load_config():
    """
    Load the configuration settings from the `settings.toml` and `secrets.toml` files.

    Returns:
        dict: The combined configuration settings.

    Raises:
        Exception: If any file loading or update error occurs.
    """
    # Load settings.toml
    settings_path = pathlib.Path(__file__).parent / "settings.toml"

    try:
        config = load_toml_file(settings_path)
    except Exception as e:
        raise Exception(f"Error loading settings from {settings_path}: {e}")

    # Load .secrets.toml
    CONFIG_SECRETS_FILE = os.getenv("CONFIG_SECRETS_FILE")

    if not CONFIG_SECRETS_FILE:
        secrets_path = pathlib.Path(__file__).parent / "secrets.toml"
    else:
        secrets_path = pathlib.Path(CONFIG_SECRETS_FILE)

    try:
        secrets = load_toml_file(secrets_path)
    except Exception as e:
        raise Exception(f"Error loading secrets from {secrets_path}: {e}")

    # Update config with secrets
    config.update(secrets)

    # Set MODE based on environment variable
    config["MODE"] = os.getenv("MODE", "STABLE")

    return config


# Load the configuration when the module is initialized
config = load_config()
