"""Small, dependency-free configuration helpers for Spotify commands."""
import os
from pathlib import Path
import re


CLIENT_ID = re.compile(r"[A-Fa-f0-9]{32}\Z")


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def dotenv_client_id(path=None):
    """Read only SPOTIFY_CLIENT_ID from a local .env file."""
    path = Path(path or ".env")
    if not path.is_file():
        return None
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "SPOTIFY_CLIENT_ID":
            return _unquote(value)
    return None


def spotify_client_id(cli_value=None, env=None, dotenv_path=None):
    """Resolve and validate Client ID: CLI, environment, then local .env."""
    environment = os.environ if env is None else env
    value = cli_value or environment.get("SPOTIFY_CLIENT_ID") or dotenv_client_id(dotenv_path)
    if not value:
        raise RuntimeError(
            "Set SPOTIFY_CLIENT_ID in .env/the environment, or pass --client-id. "
            "Use the public Client ID, never a Client Secret."
        )
    value = value.strip()
    if not CLIENT_ID.fullmatch(value):
        raise RuntimeError("Invalid Spotify Client ID; expected 32 hexadecimal characters.")
    return value
