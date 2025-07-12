import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from spotify_to_ytmusic.settings import BACKUP_LOG_FILE


def migrate_old_backup_file():
    """Migrate backup file from old location to new cache directory"""
    old_backup_path = Path.cwd() / "backup" / "playlist_operations.json"
    
    if old_backup_path.exists() and not BACKUP_LOG_FILE.exists():
        try:
            # Ensure the cache directory exists
            BACKUP_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy the file to the new location
            import shutil
            shutil.copy2(old_backup_path, BACKUP_LOG_FILE)
            
            print(f"Migrated backup file from {old_backup_path} to {BACKUP_LOG_FILE}")
            print(f"You can safely delete the old backup directory: {old_backup_path.parent}")
            
            return True
        except Exception as e:
            print(f"Warning: Could not migrate backup file: {e}")
            return False
    
    return False


class PlaylistLogger:
    def __init__(self):
        # Migrate old backup file if it exists
        migrate_old_backup_file()
        
        # Use the same cache directory where credentials are stored
        self.log_file = BACKUP_LOG_FILE
        # Ensure the parent directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.logs = self.load_logs()

    def load_logs(self) -> Dict:
        """Load existing logs from file"""
        try:
            with self.log_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"operations": [], "playlist_states": {}}

    def save_logs(self):
        """Save logs to file"""
        with self.log_file.open("w", encoding="utf-8") as f:
            json.dump(self.logs, f, ensure_ascii=False, indent=2)

    def _generate_track_hash(self, tracks: List[Dict]) -> str:
        """Generate a hash from track list to detect changes"""
        track_signatures = []
        for track in tracks:
            # Create signature from artist + name (normalized)
            signature = f"{track.get('artist', '').lower().strip()}|{track.get('name', '').lower().strip()}"
            track_signatures.append(signature)
        
        # Hash the ordered list of signatures
        content = "|".join(track_signatures)
        return hashlib.md5(content.encode()).hexdigest()

    def log_playlist_operation(self, operation_type: str, spotify_playlist_name: str, 
                             youtube_playlist_name: str, tracks: List[Dict], 
                             youtube_playlist_id: str = None, success: bool = True, 
                             tracks_found: int = None, tracks_total: int = None):
        """Log a playlist operation (create/update)"""
        timestamp = datetime.now().isoformat()
        track_hash = self._generate_track_hash(tracks)
        
        operation = {
            "timestamp": timestamp,
            "operation": operation_type,  # "create", "update", "all-saved", "update-all"
            "spotify_name": spotify_playlist_name,
            "youtube_name": youtube_playlist_name,
            "youtube_id": youtube_playlist_id,
            "track_hash": track_hash,
            "tracks_total": int(tracks_total or len(tracks)),
            "tracks_found": int(tracks_found or len(tracks)),
            "success": success
        }
        
        self.logs["operations"].append(operation)
        
        # Update playlist state
        if success:
            self.logs["playlist_states"][youtube_playlist_name] = {
                "last_updated": timestamp,
                "track_hash": track_hash,
                "tracks_total": int(tracks_total or len(tracks)),
                "tracks_found": int(tracks_found or len(tracks)),
                "youtube_id": youtube_playlist_id,
                "operation": operation_type
            }
        
        self.save_logs()

    def populate_initial_state(self, youtube_playlist_name: str, spotify_tracks: List[Dict],
                             youtube_playlist_id: str, youtube_track_count: int,
                             spotify_playlist_name: str = None):
        """Populate initial state for existing playlist without operation log"""
        timestamp = datetime.now().isoformat()
        track_hash = self._generate_track_hash(spotify_tracks)
        
        # Add to playlist states for tracking
        self.logs["playlist_states"][youtube_playlist_name] = {
            "last_updated": timestamp,
            "track_hash": track_hash,
            "tracks_total": int(len(spotify_tracks)),
            "tracks_found": int(youtube_track_count),
            "youtube_id": youtube_playlist_id,
            "operation": "initial-setup",
            "spotify_name": spotify_playlist_name or youtube_playlist_name
        }
        
        # Add a minimal operation log for reference
        operation = {
            "timestamp": timestamp,
            "operation": "initial-setup",
            "spotify_name": spotify_playlist_name or youtube_playlist_name,
            "youtube_name": youtube_playlist_name,
            "youtube_id": youtube_playlist_id,
            "track_hash": track_hash,
            "tracks_total": int(len(spotify_tracks)),
            "tracks_found": int(youtube_track_count),
            "success": True
        }
        
        self.logs["operations"].append(operation)
        self.save_logs()

    def is_playlist_already_tracked(self, youtube_playlist_name: str) -> bool:
        """Check if playlist is already being tracked in logs"""
        return youtube_playlist_name in self.logs["playlist_states"]

    def is_playlist_up_to_date(self, spotify_playlist_name: str, tracks: List[Dict], 
                             youtube_playlist_name: str = None, 
                             current_youtube_track_count: int = None) -> Optional[Dict]:
        """Check if playlist is up to date based on logs"""
        playlist_name = youtube_playlist_name or spotify_playlist_name
        
        if playlist_name not in self.logs["playlist_states"]:
            return None
        
        state = self.logs["playlist_states"][playlist_name]
        current_spotify_count = len(tracks)
        
        # Quick size check first (if YouTube track count provided)
        if current_youtube_track_count is not None:
            try:
                logged_youtube_count = int(state.get("tracks_found", 0) or 0)
                logged_spotify_count = int(state.get("tracks_total", 0) or 0)
                current_spotify_count = int(current_spotify_count or 0)
                current_youtube_track_count = int(current_youtube_track_count or 0)
            except (ValueError, TypeError):
                # If conversion fails, fall back to hash comparison
                pass
            else:
                # If current Spotify count differs significantly from logged, likely changed
                if abs(current_spotify_count - logged_spotify_count) > max(1, logged_spotify_count * 0.02):  # 2% tolerance
                    return {
                        "up_to_date": False,
                        "last_updated": state["last_updated"],
                        "tracks_found": logged_youtube_count,
                        "tracks_total": logged_spotify_count,
                        "size_changed": True,
                        "reason": f"Spotify tracks changed: {logged_spotify_count} → {current_spotify_count}"
                    }
                
                # If current YouTube count differs significantly from logged, likely changed
                if abs(current_youtube_track_count - logged_youtube_count) > max(1, logged_youtube_count * 0.02):
                    return {
                        "up_to_date": False,
                        "last_updated": state["last_updated"],
                        "tracks_found": logged_youtube_count,
                        "tracks_total": logged_spotify_count,
                        "size_changed": True,
                        "reason": f"YouTube tracks changed: {logged_youtube_count} → {current_youtube_track_count}"
                    }
        
        # If sizes look similar, check content hash
        current_hash = self._generate_track_hash(tracks)
        
        if state["track_hash"] == current_hash:
            return {
                "up_to_date": True,
                "last_updated": state["last_updated"],
                "tracks_found": state["tracks_found"],
                "tracks_total": state["tracks_total"]
            }
        
        return {
            "up_to_date": False,
            "last_updated": state["last_updated"],
            "tracks_found": state["tracks_found"],
            "tracks_total": state["tracks_total"],
            "hash_changed": True,
            "reason": "Track content/order changed"
        }

    def get_playlist_history(self, youtube_playlist_name: str) -> List[Dict]:
        """Get operation history for a specific playlist"""
        return [op for op in self.logs["operations"] 
                if op["youtube_name"] == youtube_playlist_name]

    def clean_old_logs(self, days: int = 30):
        """Remove logs older than specified days"""
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        self.logs["operations"] = [
            op for op in self.logs["operations"]
            if datetime.fromisoformat(op["timestamp"]).timestamp() > cutoff_date
        ]
        
        self.save_logs()

    def get_stats(self) -> Dict:
        """Get statistics about operations"""
        operations = self.logs["operations"]
        if not operations:
            return {"total_operations": 0}
        
        return {
            "total_operations": len(operations),
            "total_playlists": len(self.logs["playlist_states"]),
            "successful_operations": len([op for op in operations if op["success"]]),
            "failed_operations": len([op for op in operations if not op["success"]]),
            "last_operation": operations[-1]["timestamp"] if operations else None,
            "operations_by_type": {
                op_type: len([op for op in operations if op["operation"] == op_type])
                for op_type in set(op["operation"] for op in operations)
            }
        }

    def get_log_location(self) -> str:
        """Get the path where the playlist logs are stored"""
        return str(self.log_file)

    def get_log_size(self) -> int:
        """Get the size of the log file in bytes"""
        try:
            return self.log_file.stat().st_size if self.log_file.exists() else 0
        except OSError:
            return 0
