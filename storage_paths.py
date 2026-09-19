"""Data defaults outside Documents/OneDrive; explicit CLI paths still take priority."""
import os
from pathlib import Path


def data_root():
    override = os.environ.get("PERSONAL_MUSIC_LIBRARY_DATA")
    if override:
        return Path(override).expanduser().resolve()
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".local" / "share"
    return base / "PersonalMusicLibrary"
