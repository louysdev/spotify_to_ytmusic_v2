import configparser
import platform
from pathlib import Path

import platformdirs

CACHE_DIR = Path(
    platformdirs.user_cache_dir(
        appname="spotify_to_ytmusic", appauthor=False, ensure_exists=True
    )
)
SPOTIPY_CACHE_FILE = CACHE_DIR / "spotipy.cache"
DEFAULT_PATH = CACHE_DIR / "settings.ini"
EXAMPLE_PATH = Path(__file__).parent / "settings.ini.example"

# Log files
# All log files are now stored in the same cache directory as credentials
# This ensures better organization and follows platform conventions
BACKUP_LOG_FILE = CACHE_DIR / "playlist_operations.json"
NO_RESULTS_LOG_FILE = CACHE_DIR / "noresults_youtube.txt"


def get_cache_directory() -> Path:
    """Get the cache directory path where logs and credentials are stored"""
    return CACHE_DIR


def get_log_files_info() -> dict:
    """Get information about log file locations"""
    return {
        "cache_directory": str(CACHE_DIR),
        "backup_log": str(BACKUP_LOG_FILE),
        "no_results_log": str(NO_RESULTS_LOG_FILE),
        "settings_file": str(DEFAULT_PATH),
        "spotify_cache": str(SPOTIPY_CACHE_FILE),
        "platform": platform.system(),
        "platformdirs_version": platformdirs.__version__ if hasattr(platformdirs, '__version__') else "unknown",
    }


class Settings:
    config: configparser.ConfigParser
    filepath: Path = DEFAULT_PATH

    def __init__(self, filepath: Path | None = None):
        self.config = configparser.ConfigParser(interpolation=None)
        if filepath:
            self.filepath = filepath
        if not self.filepath.is_file():
            raise FileNotFoundError(
                "No settings.ini found! Please run \n\n spotify_to_ytmusic setup"
            )
        self.config.read(self.filepath)

    def __getitem__(self, key):
        return self.config[key]

    def __setitem__(self, section, key, value):
        self.config.set(section, key, value)

    def save(self):
        with open(self.filepath, "w") as f:
            self.config.write(f)

def migrate_legacy_cache_files(verbose=False):
    """
    Migrate cache files from legacy locations to the current platform-specific location.
    This ensures compatibility across different operating systems.
    
    Args:
        verbose: If True, print detailed information about the migration process
    """
    import os
    import shutil
    from pathlib import Path
    
    # Possible legacy locations based on different OS conventions
    legacy_locations = []
    
    # Linux/Unix style - ~/.cache/spotify_to_ytmusic/
    home = Path.home()
    linux_cache = home / ".cache" / "spotify_to_ytmusic"
    if linux_cache.exists():
        legacy_locations.append(("Linux cache", linux_cache))
    
    # macOS style - ~/Library/Caches/spotify_to_ytmusic/
    macos_cache = home / "Library" / "Caches" / "spotify_to_ytmusic"
    if macos_cache.exists() and macos_cache != CACHE_DIR:
        legacy_locations.append(("macOS cache", macos_cache))
    
    # Windows style - %LOCALAPPDATA%/spotify_to_ytmusic/
    if os.name == 'nt':
        localappdata = os.environ.get('LOCALAPPDATA')
        if localappdata:
            windows_cache = Path(localappdata) / "spotify_to_ytmusic"
            if windows_cache.exists() and windows_cache != CACHE_DIR:
                legacy_locations.append(("Windows cache", windows_cache))
    
    # Current working directory (old behavior)
    cwd_backup = Path.cwd() / "backup"
    if cwd_backup.exists():
        legacy_locations.append(("CWD backup", cwd_backup))
    
    migrated_files = []
    
    for location_name, legacy_path in legacy_locations:
        if not legacy_path.exists():
            continue
            
        if verbose:
            print(f"🔍 Found legacy cache location: {location_name} at {legacy_path}")
        
        # Files to migrate
        legacy_files = {
            "settings.ini": DEFAULT_PATH,
            "spotipy.cache": SPOTIPY_CACHE_FILE,
            "playlist_operations.json": BACKUP_LOG_FILE,
            "noresults_youtube.txt": NO_RESULTS_LOG_FILE,
            "lookup.json": CACHE_DIR / "lookup.json"
        }
        
        for legacy_filename, target_path in legacy_files.items():
            legacy_file = legacy_path / legacy_filename
            
            if legacy_file.exists() and not target_path.exists():
                try:
                    # Ensure target directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file to new location
                    shutil.copy2(legacy_file, target_path)
                    migrated_files.append(f"{legacy_filename} from {location_name}")
                    if verbose:
                        print(f"  ✅ Migrated {legacy_filename}")
                    
                except Exception as e:
                    if verbose:
                        print(f"  ❌ Failed to migrate {legacy_filename}: {e}")
    
    if migrated_files and verbose:
        print(f"\n🎉 Successfully migrated {len(migrated_files)} files:")
        for file in migrated_files:
            print(f"   - {file}")
        print(f"\n📂 All files are now in: {CACHE_DIR}")
        print("💡 You can safely delete the old cache directories after verifying everything works.")
    
    return len(migrated_files) > 0
