import configparser
import platform
import os
from pathlib import Path

import platformdirs

# Force consistent cache directory detection across all platforms and installations
def get_consistent_cache_dir():
    """
    Get a consistent cache directory that works across different installations
    and platforms. This ensures that pipx installations find the same cache.
    """
    # Use platformdirs with consistent parameters
    cache_dir = platformdirs.user_cache_dir(
        appname="spotify_to_ytmusic", 
        appauthor=False,  # Explicitly set to False
        ensure_exists=True
    )
    
    # Convert to Path object
    cache_path = Path(cache_dir)
    
    # Ensure directory exists
    cache_path.mkdir(parents=True, exist_ok=True)
    
    return cache_path

CACHE_DIR = get_consistent_cache_dir()
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
        "cache_dir_exists": CACHE_DIR.exists(),
        "backup_log_exists": BACKUP_LOG_FILE.exists(),
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

def ensure_cache_directory_exists():
    """Ensure the cache directory exists and is writable"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"Warning: Could not create cache directory {CACHE_DIR}: {e}")
        return False


def debug_cache_paths():
    """Debug function to show detailed cache path information"""
    import os
    
    print(f"🔍 Debug: Cache Path Detection")
    print(f"Platform: {platform.system()}")
    print(f"User home: {Path.home()}")
    print(f"Current working directory: {Path.cwd()}")
    
    # Show platformdirs detection with different parameters
    cache_dir_no_ensure = platformdirs.user_cache_dir(
        appname="spotify_to_ytmusic", appauthor=False, ensure_exists=False
    )
    cache_dir_with_ensure = platformdirs.user_cache_dir(
        appname="spotify_to_ytmusic", appauthor=False, ensure_exists=True
    )
    
    print(f"Platformdirs cache dir (no ensure): {cache_dir_no_ensure}")
    print(f"Platformdirs cache dir (with ensure): {cache_dir_with_ensure}")
    print(f"CACHE_DIR constant: {CACHE_DIR}")
    print(f"Cache dir exists: {CACHE_DIR.exists()}")
    print(f"Cache dir is writable: {os.access(CACHE_DIR, os.W_OK) if CACHE_DIR.exists() else 'N/A'}")
    
    if CACHE_DIR.exists():
        files_in_cache = list(CACHE_DIR.iterdir())
        print(f"Files in cache dir: {[f.name for f in files_in_cache]}")
    
    # Environment variables that might affect cache location
    env_vars = ['HOME', 'XDG_CACHE_HOME', 'LOCALAPPDATA', 'APPDATA']
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            print(f"ENV {var}: {value}")
    
    # Test consistency
    cache_test_1 = get_consistent_cache_dir()
    cache_test_2 = get_consistent_cache_dir()
    print(f"Consistency test: {cache_test_1 == cache_test_2} ({cache_test_1} == {cache_test_2})")

def create_cross_platform_symlinks():
    """
    Create symlinks or reference files to help with cross-platform cache discovery.
    This is particularly useful for systems where platformdirs might give different results.
    """
    import os
    
    # Only create symlinks on Unix-like systems
    if os.name != 'posix':
        return False
    
    # Potential alternative cache locations
    home = Path.home()
    alternative_locations = [
        home / ".cache" / "spotify_to_ytmusic",  # Standard Linux
        home / ".spotify_to_ytmusic",            # Fallback location
    ]
    
    created_links = []
    
    for alt_location in alternative_locations:
        if alt_location != CACHE_DIR and not alt_location.exists():
            try:
                # Create parent directory if it doesn't exist
                alt_location.parent.mkdir(parents=True, exist_ok=True)
                
                # Create symlink to the actual cache directory
                alt_location.symlink_to(CACHE_DIR)
                created_links.append(str(alt_location))
            except Exception as e:
                # If symlink fails, create a reference file instead
                try:
                    reference_file = alt_location.parent / f"{alt_location.name}_location.txt"
                    reference_file.write_text(f"Cache directory is at: {CACHE_DIR}\n")
                    created_links.append(f"reference: {reference_file}")
                except Exception:
                    pass  # Ignore if we can't create reference either
    
    return created_links


def find_cache_directory_across_platforms():
    """
    Robust cache directory finder that checks multiple possible locations.
    Returns the first valid cache directory found.
    """
    # Primary location (current platformdirs detection)
    primary_cache = CACHE_DIR
    if primary_cache.exists() and (primary_cache / "playlist_operations.json").exists():
        return primary_cache
    
    # Alternative locations to check
    home = Path.home()
    alternative_locations = []
    
    if platform.system() == "Linux":
        alternative_locations = [
            home / ".cache" / "spotify_to_ytmusic",
            home / ".spotify_to_ytmusic",
            home / ".local" / "share" / "spotify_to_ytmusic",
        ]
    elif platform.system() == "Darwin":  # macOS
        alternative_locations = [
            home / "Library" / "Caches" / "spotify_to_ytmusic",
            home / ".cache" / "spotify_to_ytmusic",
        ]
    elif platform.system() == "Windows":
        import os
        localappdata = os.environ.get('LOCALAPPDATA', '')
        appdata = os.environ.get('APPDATA', '')
        alternative_locations = [
            Path(localappdata) / "spotify_to_ytmusic" if localappdata else None,
            Path(appdata) / "spotify_to_ytmusic" if appdata else None,
            home / "AppData" / "Local" / "spotify_to_ytmusic",
        ]
        alternative_locations = [loc for loc in alternative_locations if loc]
    
    # Check alternative locations
    for alt_cache in alternative_locations:
        if alt_cache and alt_cache.exists() and (alt_cache / "playlist_operations.json").exists():
            print(f"Found cache in alternative location: {alt_cache}")
            return alt_cache
    
    # If no existing cache found, return the primary location
    return primary_cache
