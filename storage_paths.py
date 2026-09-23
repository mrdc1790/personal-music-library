"""Data defaults outside Documents/OneDrive; explicit CLI paths still take priority."""
import os
from pathlib import Path


def data_root():
    override = os.environ.get("PERSONAL_MUSIC_LIBRARY_DATA")
    if override:
        return Path(override).expanduser().resolve()
    # Packaged desktop processes can virtualize LOCALAPPDATA (and registry reads).
    # Use the user's physical profile consistently; the explicit override wins.
    if os.name == 'nt' and os.environ.get('USERPROFILE'):
        return Path(os.environ['USERPROFILE']) / 'MusicLibraryData'
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".local" / "share"
    return base / "PersonalMusicLibrary"
