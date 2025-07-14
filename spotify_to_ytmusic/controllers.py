import re
import time
import threading
import select
import sys
from datetime import datetime

import spotipy

from spotify_to_ytmusic.setup import setup as setup_func
from spotify_to_ytmusic.spotify import Spotify
from spotify_to_ytmusic.ytmusic import YTMusicTransfer
from spotify_to_ytmusic.utils.playlist_logger import PlaylistLogger
from spotify_to_ytmusic.settings import get_log_files_info


def show_log_location(args):
    """Show the user where log files are stored"""
    from spotify_to_ytmusic.settings import migrate_legacy_cache_files
    
    # Try to migrate legacy cache files first (verbose mode)
    migrated = migrate_legacy_cache_files(verbose=True)
    if migrated:
        print()  # Add spacing after migration output
    
    log_info = get_log_files_info()
    print(f"📂 Log files and credentials are stored in:")
    print(f"Platform: {log_info['platform']}")
    print(f"Cache directory: {log_info['cache_directory']}")
    print(f"- Settings file: {log_info['settings_file']}")
    print(f"- Spotify cache: {log_info['spotify_cache']}")
    print(f"- Playlist operations log: {log_info['backup_log']}")
    print(f"- No results log: {log_info['no_results_log']}")
    print(f"\n💡 This location is automatically detected for your operating system.")
    print(f"   If you're using multiple systems, each will have its own cache directory.")
    
    # Check if files actually exist
    from pathlib import Path
    files_to_check = [
        ("Settings", log_info['settings_file']),
        ("Spotify cache", log_info['spotify_cache']),
        ("Playlist log", log_info['backup_log']),
        ("No results log", log_info['no_results_log'])
    ]
    
    existing_files = []
    missing_files = []
    
    for name, filepath in files_to_check:
        if Path(filepath).exists():
            existing_files.append(name)
        else:
            missing_files.append(name)
    
    if existing_files:
        print(f"\n✅ Existing files: {', '.join(existing_files)}")
    if missing_files:
        print(f"⚠️  Missing files: {', '.join(missing_files)} (will be created when needed)")


def _get_spotify_playlist(spotify, playlist):
    try:
        return spotify.getSpotifyPlaylist(playlist)
    except Exception as ex:
        print(
            "Could not get Spotify playlist. Please check the playlist link.\n Error: "
            + repr(ex)
        )
        return


def _print_success(name, playlistId):
    print(
        f"Success: created playlist '{name}' at\n"
        f"https://music.youtube.com/playlist?list={playlistId}"
    )
    # Show where logs are stored on first success
    try:
        logger = PlaylistLogger()
        print(f"Operation logged to: {logger.get_log_location()}")
    except Exception:
        pass  # Silently fail for logging location display


def _init():
    return Spotify(), YTMusicTransfer()


def all(args):
    spotify, ytmusic = _init()
    pl = spotify.getUserPlaylists(args.user)
    print(str(len(pl)) + " playlists found. Starting transfer...")
    count = 1
    for p in pl:
        print("Playlist " + str(count) + ": " + p["name"])
        count = count + 1
        try:
            playlist = spotify.getSpotifyPlaylist(p["external_urls"]["spotify"])
            videoIds = ytmusic.search_songs(
                playlist["tracks"], use_cached=args.use_cached
            )
            playlist_id = ytmusic.create_playlist(
                p["name"],
                p["description"],
                "PUBLIC" if p["public"] else "PRIVATE",
                videoIds,
            )
            if args.like:
                for id in videoIds:
                    ytmusic.rate_song(id, "LIKE")
            _print_success(p["name"], playlist_id)
        except Exception as ex:
            print(f"Could not transfer playlist {p['name']}. {ex!s}")


def _create_ytmusic(args, playlist, ytmusic, operation_type="create"):
    try:
        logger = PlaylistLogger()
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize logging: {e}")
        logger = None
    
    date = ""
    if args.date:
        date = " " + datetime.today().strftime("%m/%d/%Y")
    name = args.name + date if args.name else playlist["name"] + date
    info = playlist["description"] if (args.info is None) else args.info
    
    videoIds = ytmusic.search_songs(playlist["tracks"], use_cached=args.use_cached)
    tracks_found = len([vid for vid in videoIds if vid])  # Count non-empty videoIds
    
    if args.like:
        for id in videoIds:
            ytmusic.rate_song(id, "LIKE")

    playlistId = ytmusic.create_playlist(
        name, info, "PUBLIC" if args.public else "PRIVATE", videoIds
    )
    
    # Log the operation
    if logger:
        logger.log_playlist_operation(
            operation_type=operation_type,
            spotify_playlist_name=playlist["name"],
            youtube_playlist_name=name,
            tracks=playlist["tracks"],
            youtube_playlist_id=playlistId,
            success=True,
            tracks_found=tracks_found,
            tracks_total=len(playlist["tracks"])
        )
    
    _print_success(name, playlistId)


def create(args):
    spotify, ytmusic = _init()
    playlist = _get_spotify_playlist(spotify, args.playlist)
    _create_ytmusic(args, playlist, ytmusic, "create")


def liked(args):
    spotify, ytmusic = _init()
    if not isinstance(spotify.api.auth_manager, spotipy.SpotifyOAuth):
        raise Exception("OAuth not configured, please run setup and set OAuth to 'yes'")
    playlist = spotify.getLikedPlaylist()
    _create_ytmusic(args, playlist, ytmusic, "liked")


def all_saved(args):
    spotify, ytmusic = _init()
    
    # Initialize logger with error handling
    try:
        logger = PlaylistLogger()
        print(f"📋 Using log file: {logger.get_log_location()}")
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize PlaylistLogger: {e}")
        print("Continuing without logging...")
        logger = None
    
    if not isinstance(spotify.api.auth_manager, spotipy.SpotifyOAuth):
        raise Exception("OAuth not configured, please run setup and set OAuth to 'yes'")
    
    # Collect all playlists from different sources
    all_playlists = []
    
    # Get current user's saved playlists
    saved_playlists = spotify.getAllSavedPlaylists()
    all_playlists.extend(saved_playlists)
    print(f"{len(saved_playlists)} saved playlists found from current user")
    
    # Get saved albums automatically
    try:
        saved_albums = spotify.getSavedAlbums()
        all_playlists.extend(saved_albums)
        print(f"{len(saved_albums)} saved albums found")
    except Exception as ex:
        print(f"Could not get saved albums: {ex}")
    
    # Get playlists from target user if specified
    if args.target_user:
        try:
            target_user_playlists = spotify.getUserPlaylists(args.target_user)
            all_playlists.extend(target_user_playlists)
            print(f"{len(target_user_playlists)} public playlists found from user '{args.target_user}'")
        except Exception as ex:
            print(f"Could not get playlists from user '{args.target_user}': {ex}")
    
    print(f"Total: {len(all_playlists)} playlists to process. Starting transfer...")
    
    count = 1
    transferred = 0
    skipped = 0
    
    for i, p in enumerate(all_playlists):
        # Batch processing with delays
        if i > 0 and i % args.batch_size == 0:
            print(f"Processed {i} playlists. Waiting {args.batch_delay} seconds...")
            time.sleep(args.batch_delay)
        
        owner_name = p['owner']['display_name'] if 'owner' in p else 'Unknown'
        playlist_name = p["name"]
        
        # Check if playlist already exists in YouTube Music (similar name matching)
        existing_playlist = ytmusic.playlist_exists(playlist_name)
        if existing_playlist:
            if existing_playlist == playlist_name:
                print(f"Playlist {count}: '{playlist_name}' already exists - SKIPPED")
            else:
                print(f"Playlist {count}: '{playlist_name}' similar to existing '{existing_playlist}' - SKIPPED")
            skipped += 1
            count += 1
            continue
        
        # Skip playlists with too many tracks (> 5000 for performance)
        track_count = len(p.get("tracks", [])) if isinstance(p.get("tracks"), list) else p.get("tracks", {}).get("total", 0)
        if track_count > 5000:
            print(f"Playlist {count}: '{playlist_name}' has {track_count} tracks - SKIPPED (too large)")
            skipped += 1
            count += 1
            continue
        
        content_type = "Album" if p.get("type") == "album" else "Playlist"
        print(f"{content_type} {count}: '{playlist_name}' (by {owner_name}) - {track_count} tracks")
        count += 1
        
        try:
            # For albums, we already have the tracks, for playlists we need to fetch them
            if p.get("type") == "album":
                playlist = {
                    "tracks": p["tracks"],
                    "name": playlist_name,
                    "description": p["description"]
                }
            else:
                playlist = spotify.getSpotifyPlaylist(p["external_urls"]["spotify"])
            
            videoIds = ytmusic.search_songs(
                playlist["tracks"], use_cached=args.use_cached
            )
            tracks_found = len([vid for vid in videoIds if vid])
            
            playlist_id = ytmusic.create_playlist(
                playlist_name,
                playlist.get("description", ""),
                "PUBLIC" if args.public else "PRIVATE",
                videoIds,
            )
            if args.like:
                for id in videoIds:
                    ytmusic.rate_song(id, "LIKE")
            
            # Log the operation
            if logger:
                logger.log_playlist_operation(
                    operation_type="all-saved",
                    spotify_playlist_name=p["name"],
                    youtube_playlist_name=playlist_name,
                    tracks=playlist["tracks"],
                    youtube_playlist_id=playlist_id,
                    success=True,
                    tracks_found=tracks_found,
                    tracks_total=len(playlist["tracks"])
                )
            
            _print_success(playlist_name, playlist_id)
            transferred += 1
        except Exception as ex:
            # Log failed operation
            if logger:
                logger.log_playlist_operation(
                    operation_type="all-saved",
                    spotify_playlist_name=p["name"],
                    youtube_playlist_name=playlist_name,
                    tracks=playlist.get("tracks", []),
                    success=False,
                    tracks_found=0,
                    tracks_total=len(playlist.get("tracks", []))
                )
            print(f"Could not transfer {content_type.lower()} '{playlist_name}'. {ex}")


def update(args):
    spotify, ytmusic = _init()
    playlist = _get_spotify_playlist(spotify, args.playlist)
    playlistId = ytmusic.get_playlist_id(args.name)
    videoIds = ytmusic.search_songs(playlist["tracks"], use_cached=args.use_cached)
    if not args.append:
        ytmusic.remove_songs(playlistId)
    time.sleep(2)
    ytmusic.add_playlist_items(playlistId, videoIds)


def update_all(args):
    spotify, ytmusic = _init()
    
    # Initialize logger with error handling
    try:
        logger = PlaylistLogger()
        print(f"📋 Using log file: {logger.get_log_location()}")
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize PlaylistLogger: {e}")
        print("Continuing without advanced comparison features...")
        logger = None
    
    if not logger:
        print("❌ Cannot proceed without logging. Please run 'spotify_to_ytmusic initial-setup' first.")
        return
    
    if not isinstance(spotify.api.auth_manager, spotipy.SpotifyOAuth):
        raise Exception("OAuth not configured, please run setup and set OAuth to 'yes'")
    
    # Get tracked playlists from logs instead of scanning Spotify
    print("🔍 Getting tracked playlists from logs...")
    tracked_playlists = logger.get_tracked_playlists()
    
    if not tracked_playlists:
        print("❌ No tracked playlists found in logs!")
        print("Please run 'spotify_to_ytmusic initial-setup' first to populate the logs.")
        return
    
    print(f"📋 Found {len(tracked_playlists)} tracked playlists in logs")
    print(f"Starting comparison and update process...")
    
    count = 1
    updated = 0
    skipped = 0
    not_found = 0
    failed = 0
    
    for i, tracked_playlist in enumerate(tracked_playlists):
        # Batch processing with delays
        if i > 0 and i % getattr(args, 'batch_size', 5) == 0:
            print(f"Processed {i} playlists. Waiting {getattr(args, 'batch_delay', 2)} seconds...")
            time.sleep(getattr(args, 'batch_delay', 2))
        
        # Get playlist info from the tracked data
        youtube_name = tracked_playlist.get('youtube_playlist_name')
        youtube_id = tracked_playlist.get('youtube_playlist_id')
        spotify_name = tracked_playlist.get('spotify_playlist_name')
        last_updated = tracked_playlist.get('timestamp', 'Unknown')
        
        if not youtube_name or not youtube_id:
            print(f"\n❌ Playlist {count}: Invalid tracked playlist data - SKIPPED")
            count += 1
            failed += 1
            continue
        
        print(f"\n📋 Playlist {count}: '{youtube_name}' (YouTube)")
        print(f"   🎵 Linked to Spotify: '{spotify_name}'")
        print(f"   📅 Last updated: {last_updated[:19] if last_updated != 'Unknown' else 'Unknown'}")
        count += 1
        
        # Try to find the current Spotify playlist by name
        print(f"  🔍 Searching for current Spotify playlist...")
        spotify_playlist = None
        spotify_tracks = []
        
        # Get all current Spotify playlists to find a match
        try:
            saved_playlists = spotify.getAllSavedPlaylists()
            saved_albums = spotify.getSavedAlbums()
            all_current_spotify = saved_playlists + saved_albums
            
            # Try to find matching Spotify playlist/album
            for sp_item in all_current_spotify:
                if sp_item["name"].lower() == spotify_name.lower():
                    spotify_playlist = sp_item
                    break
            
            if spotify_playlist:
                print(f"  ✅ Found matching Spotify playlist: '{spotify_playlist['name']}'")
                
                # Get Spotify tracks
                if spotify_playlist.get("type") == "album":
                    spotify_tracks = spotify_playlist["tracks"]
                else:
                    full_playlist = spotify.getSpotifyPlaylist(spotify_playlist["external_urls"]["spotify"])
                    spotify_tracks = full_playlist["tracks"]
            else:
                print(f"  ⚠️  Spotify playlist '{spotify_name}' not found in current library")
                print(f"     This might mean the playlist was deleted or renamed in Spotify")
                not_found += 1
                continue
                
        except Exception as ex:
            print(f"  ❌ Error getting Spotify playlist: {ex}")
            failed += 1
            continue
        
        # Get YouTube Music tracks for comparison
        try:
            print(f"  🔍 Getting YouTube Music playlist tracks...")
            youtube_tracks = ytmusic.get_playlist_tracks(youtube_id)
            print(f"  📊 Spotify: {len(spotify_tracks)} tracks, YouTube: {len(youtube_tracks)} tracks")
        except Exception as ex:
            print(f"  ❌ Error getting YouTube Music tracks: {ex}")
            failed += 1
            continue
        
        # Check if playlist is up to date based on logs (fast check)
        try:
            log_status = logger.is_playlist_up_to_date(
                spotify_name,
                spotify_tracks, 
                youtube_name, 
                len(youtube_tracks)
            )
            
            if log_status and log_status.get("up_to_date"):
                print(f"  ✅ Up-to-date (last checked: {log_status['last_updated'][:10]}) - SKIPPED")
                skipped += 1
                continue
            elif log_status and log_status.get("size_changed"):
                print(f"  📋 Size change detected: {log_status.get('reason', 'Unknown')}")
            elif log_status and log_status.get("hash_changed"):
                print(f"  📋 Content change detected (last updated: {log_status['last_updated'][:10]})")
            else:
                print(f"  📋 No recent log history, performing full comparison")
                
        except Exception as ex:
            print(f"  ⚠️  Could not check log status: {ex}")
        
        # Determine which Spotify tracks are actually available in YouTube Music
        print(f"  🔍 Checking track availability...")
        try:
            videoIds = ytmusic.search_songs(spotify_tracks, use_cached=getattr(args, 'use_cached', False))
            available_spotify_tracks = []
            
            # Map successful matches back to original tracks
            for idx, spotify_track in enumerate(spotify_tracks):
                if idx < len(videoIds) and videoIds[idx]:  # videoIds[idx] is not None/empty
                    available_spotify_tracks.append(spotify_track)
            
            print(f"  📊 Available tracks - Spotify: {len(available_spotify_tracks)}, YouTube: {len(youtube_tracks)}")
            
        except Exception as ex:
            print(f"  ❌ Error checking track availability: {ex}")
            failed += 1
            continue
        
        # Compare tracks and decide if update is needed
        try:
            tracks_match = True
            significant_difference = False
            
            # If YouTube has significantly fewer tracks than what's available from Spotify,
            # or more tracks, then it needs updating
            availability_ratio = len(youtube_tracks) / len(available_spotify_tracks) if len(available_spotify_tracks) > 0 else 0
            
            if availability_ratio < 0.95 or availability_ratio > 1.05:  # More than 5% difference
                significant_difference = True
                print(f"  ⚠️  Significant track count difference: {availability_ratio:.2%} ratio")
            
            # Check track order for available songs (if no significant difference)
            if not significant_difference and len(available_spotify_tracks) > 0 and len(youtube_tracks) > 0:
                comparison_length = min(len(available_spotify_tracks), len(youtube_tracks))
                order_matches = 0
                
                for idx in range(min(comparison_length, 10)):  # Compare first 10 tracks for performance
                    if idx < len(available_spotify_tracks) and idx < len(youtube_tracks):
                        spotify_track = available_spotify_tracks[idx]
                        youtube_track = youtube_tracks[idx]
                        if ytmusic.compare_track_similarity(spotify_track, youtube_track):
                            order_matches += 1
                
                # Consider tracks matching if at least the specified tolerance of compared tracks match in order
                tolerance = getattr(args, 'tolerance', 0.9)
                match_ratio = order_matches / min(comparison_length, 10) if comparison_length > 0 else 1
                tracks_match = match_ratio >= tolerance
                
                print(f"  📈 Track order match: {order_matches}/{min(comparison_length, 10)} ({match_ratio:.1%}) - Tolerance: {tolerance:.1%}")
            else:
                tracks_match = False
            
            if tracks_match and not significant_difference:
                print(f"  ✅ Tracks match sufficiently - SKIPPED")
                skipped += 1
                continue
            
            # Update playlist if tracks don't match significantly
            print(f"  🔄 Updating playlist...")
            
            if not getattr(args, 'append', False):
                ytmusic.remove_songs(youtube_id)
                time.sleep(2)
            
            ytmusic.add_playlist_items(youtube_id, videoIds)
            
            # Log the successful update
            logger.log_playlist_operation(
                operation_type="update-all",
                spotify_playlist_name=spotify_name,
                youtube_playlist_name=youtube_name,
                tracks=spotify_tracks,
                youtube_playlist_id=youtube_id,
                success=True,
                tracks_found=len(available_spotify_tracks),
                tracks_total=len(spotify_tracks)
            )
            
            print(f"  ✅ Updated successfully")
            updated += 1
            
        except Exception as ex:
            # Log failed update
            logger.log_playlist_operation(
                operation_type="update-all",
                spotify_playlist_name=spotify_name,
                youtube_playlist_name=youtube_name,
                tracks=spotify_tracks,
                success=False,
                tracks_found=0,
                tracks_total=len(spotify_tracks)
            )
            print(f"  ❌ Could not update: {ex!s}")
            failed += 1
    
    print(f"\nUpdate completed:")
    print(f"✅ Updated: {updated}")
    print(f"⏭️  Already up-to-date: {skipped}")
    print(f"❌ Not found in Spotify: {not_found}")
    print(f"💥 Failed: {failed}")


def remove(args):
    ytmusic = YTMusicTransfer()
    ytmusic.remove_playlists(args.pattern)


def search(args):
    spotify, ytmusic = _init()
    track = spotify.getSingleTrack(args.link)
    tracks = {
        "name": track["name"],
        "artist": track["artists"][0]["name"],
        "duration": track["duration_ms"] / 1000,
        "album": track["album"]["name"],
    }

    video_id = ytmusic.search_songs([tracks], use_cached=args.use_cached)

    if not video_id:
        print("Error: No Match found.")
        return
    print(f"https://music.youtube.com/watch?v={video_id[0]}")


def cache_clear(args):
    from spotify_to_ytmusic.utils.cache_manager import CacheManager

    cacheManager = CacheManager()
    cacheManager.remove_cache_file()


def log_stats(args):
    try:
        logger = PlaylistLogger()
        stats = logger.get_stats()
        
        print("📊 Playlist Operation Statistics")
        print("=" * 40)
        print(f"Total operations: {stats['total_operations']}")
        print(f"Total playlists tracked: {stats['total_playlists']}")
        print(f"Successful operations: {stats['successful_operations']}")
        print(f"Failed operations: {stats['failed_operations']}")
        
        if stats.get('last_operation'):
            print(f"Last operation: {stats['last_operation'][:19]}")
        
        if stats.get('operations_by_type'):
            print("\nOperations by type:")
            for op_type, count in stats['operations_by_type'].items():
                print(f"  {op_type}: {count}")
        
        print(f"\nLog file location: {logger.log_file}")
    
    except Exception as e:
        print(f"❌ Could not load log statistics: {e}")
        print("This may indicate that no operations have been logged yet or there's a cache issue.")
        print("Try running 'spotify_to_ytmusic cache-debug' for more information.")


def initial_setup(args):
    """Scan existing YouTube Music playlists and populate logs for future tracking"""
    spotify, ytmusic = _init()
    
    try:
        logger = PlaylistLogger()
        print(f"📋 Using log file: {logger.get_log_location()}")
    except Exception as e:
        print(f"❌ Could not initialize PlaylistLogger: {e}")
        print("Cannot proceed with initial setup without logging capability.")
        return
    
    if not isinstance(spotify.api.auth_manager, spotipy.SpotifyOAuth):
        raise Exception("OAuth not configured, please run setup and set OAuth to 'yes'")
    
    print("🔍 Scanning existing YouTube Music playlists...")
    
    # Get all YouTube Music playlists
    try:
        youtube_playlists = ytmusic.api.get_library_playlists(10000)
        print(f"Found {len(youtube_playlists)} playlists in YouTube Music")
    except Exception as ex:
        print(f"Could not get YouTube Music playlists: {ex}")
        return
    
    # Collect Spotify playlists for matching
    print("🔍 Collecting Spotify library for matching...")
    all_spotify_playlists = []
    
    try:
        # Get saved playlists
        saved_playlists = spotify.getAllSavedPlaylists()
        all_spotify_playlists.extend(saved_playlists)
        print(f"Found {len(saved_playlists)} saved playlists in Spotify")
        
        # Get saved albums
        saved_albums = spotify.getSavedAlbums()
        all_spotify_playlists.extend(saved_albums)
        print(f"Found {len(saved_albums)} saved albums in Spotify")
        
        # Get playlists from target user if specified
        if args.target_user:
            target_user_playlists = spotify.getUserPlaylists(args.target_user)
            all_spotify_playlists.extend(target_user_playlists)
            print(f"Found {len(target_user_playlists)} public playlists from user '{args.target_user}'")
            
    except Exception as ex:
        print(f"Could not get Spotify playlists: {ex}")
        return
    
    print(f"\nTotal Spotify content: {len(all_spotify_playlists)} playlists/albums")
    print("🔄 Matching YouTube playlists with Spotify content...\n")
    
    matched = 0
    already_tracked = 0
    unmatched = 0
    
    for youtube_playlist in youtube_playlists:
        youtube_name = youtube_playlist["title"]
        youtube_id = youtube_playlist["playlistId"]
        youtube_track_count = youtube_playlist.get("count", 0)
        
        # Skip if already tracked
        if logger.is_playlist_already_tracked(youtube_name):
            print(f"⏭️  '{youtube_name}' - Already tracked")
            already_tracked += 1
            continue
        
        # Try to find matching Spotify playlist/album
        matched_spotify = None
        
        # Use the same similarity matching logic as playlist_exists
        target_words = set(re.sub(r'[^\w\s]', '', youtube_name.lower()).split())
        
        for spotify_item in all_spotify_playlists:
            spotify_name = spotify_item["name"]
            spotify_words = set(re.sub(r'[^\w\s]', '', spotify_name.lower()).split())
            
            common_words = target_words.intersection(spotify_words)
            meaningful_common = [word for word in common_words if len(word) > 2]
            
            # Same matching criteria as playlist_exists
            if (youtube_name.lower() == spotify_name.lower() or 
                len(meaningful_common) >= 2 or
                (len(target_words) <= 3 and len(common_words) >= max(2, len(target_words) * 0.7))):
                matched_spotify = spotify_item
                break
        
        if matched_spotify:
            print(f"✅ '{youtube_name}' → Spotify: '{matched_spotify['name']}'")
            
            # Get Spotify tracks
            try:
                if matched_spotify.get("type") == "album":
                    spotify_tracks = matched_spotify["tracks"]
                else:
                    spotify_playlist = spotify.getSpotifyPlaylist(matched_spotify["external_urls"]["spotify"])
                    spotify_tracks = spotify_playlist["tracks"]
                
                # Populate logs
                logger.populate_initial_state(
                    youtube_playlist_name=youtube_name,
                    spotify_tracks=spotify_tracks,
                    youtube_playlist_id=youtube_id,
                    youtube_track_count=youtube_track_count,
                    spotify_playlist_name=matched_spotify["name"]
                )
                
                matched += 1
                print(f"   📊 Spotify: {len(spotify_tracks)} tracks, YouTube: {youtube_track_count} tracks")
                
            except Exception as ex:
                print(f"   ❌ Error processing: {ex}")
                unmatched += 1
        else:
            print(f"❓ '{youtube_name}' - No Spotify match found")
            unmatched += 1
    
    print(f"\n📊 Initial Setup Summary:")
    print(f"✅ Matched and logged: {matched}")
    print(f"⏭️  Already tracked: {already_tracked}")
    print(f"❓ Unmatched: {unmatched}")
    print(f"📋 Total playlists now tracked: {matched + already_tracked}")
    
    if matched > 0:
        print(f"\n🎉 Success! Your playlists are now ready for {matched} playlists.")
        print("You can now use 'spotify_to_ytmusic update-all' to efficiently track changes.")


def setup(args):
    setup_func(args.file)


def all_sync(args):
    """
    Run all-saved and update-all commands every 1 minute indefinitely.
    Can be stopped with Ctrl+C or by killing the process.
    """
    print("🔄 Starting all-sync mode...")
    print("This will run 'all-saved' followed by 'update-all' every 1 minute.")
    print("To stop the sync process, use Ctrl+C or kill the process.\n")
    
    def run_sync_cycle():
        """Run one complete sync cycle (all-saved + update-all)"""
        try:
            print(f"🚀 Starting sync cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Run all-saved
            print("\n📥 Running all-saved...")
            all_saved(args)
            
            print("\n🔄 Running update-all...")
            update_all(args)
            
            print(f"✅ Sync cycle completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        except KeyboardInterrupt:
            print("\n⏹️  Sync interrupted by user")
            raise  # Re-raise to stop the main loop
        except Exception as ex:
            print(f"\n❌ Error during sync cycle: {ex}")
            print("Will retry in next cycle...")
    
    cycle_count = 0
    try:
        while True:
            cycle_count += 1
            print(f"\n📊 === Sync Cycle #{cycle_count} ===")
            
            run_sync_cycle()
                
            # Wait 1 minute before next cycle
            print(f"\n⏰ Waiting 1 minute until next sync cycle...")
            print(f"Next sync at: {datetime.fromtimestamp(time.time() + 60).strftime('%Y-%m-%d %H:%M:%S')}")
            
            time.sleep(60)  # Wait 1 minute
    
    except KeyboardInterrupt:
        print("\n⏹️  Sync process interrupted")
    
    finally:
        print(f"\n🏁 All-sync stopped after {cycle_count} cycle(s)")
        print("Thank you for using spotify-to-ytmusic!")


def cache_migrate(args):
    """Manually check and migrate cache files from legacy locations"""
    from spotify_to_ytmusic.settings import migrate_legacy_cache_files, get_log_files_info
    
    print("🔍 Checking for legacy cache files...")
    migrated = migrate_legacy_cache_files(verbose=True)
    
    if not migrated:
        print("✅ No legacy cache files found. All files are in the correct location.")
    
    # Show current locations
    print("\n📂 Current cache locations:")
    log_info = get_log_files_info()
    print(f"Platform: {log_info['platform']}")
    print(f"Cache directory: {log_info['cache_directory']}")
    
    # Check file existence
    from pathlib import Path
    files_to_check = [
        ("Settings", log_info['settings_file']),
        ("Spotify cache", log_info['spotify_cache']),
        ("Playlist log", log_info['backup_log']),
        ("No results log", log_info['no_results_log'])
    ]
    
    print("\n📋 File status:")
    for name, filepath in files_to_check:
        exists = Path(filepath).exists()
        status = "✅ EXISTS" if exists else "❌ MISSING"
        print(f"  {name}: {status}")
        print(f"    Path: {filepath}")


def cache_debug(args):
    """Show detailed cache directory debug information"""
    from spotify_to_ytmusic.settings import (
        debug_cache_paths, 
        ensure_cache_directory_exists, 
        get_log_files_info,
        find_cache_directory_across_platforms,
        create_cross_platform_symlinks
    )
    from spotify_to_ytmusic.utils.playlist_logger import PlaylistLogger
    
    print("🐛 Cache Directory Debug Information")
    print("=" * 50)
    
    debug_cache_paths()
    
    print(f"\n🔍 Cross-Platform Cache Detection:")
    robust_cache = find_cache_directory_across_platforms()
    print(f"Detected cache directory: {robust_cache}")
    
    print(f"\n🔗 Cross-Platform Symlinks:")
    symlinks = create_cross_platform_symlinks()
    if symlinks:
        for link in symlinks:
            print(f"  Created: {link}")
    else:
        print("  No symlinks created (not needed or not supported)")
    
    print(f"\n📁 Cache Directory Status:")
    cache_ok = ensure_cache_directory_exists()
    if cache_ok:
        print("✅ Cache directory is accessible and writable")
    else:
        print("❌ Cache directory has issues")
    
    print(f"\n📋 File Status:")
    log_info = get_log_files_info()
    
    files_to_check = [
        ("Settings", log_info['settings_file']),
        ("Spotify cache", log_info['spotify_cache']),
        ("Playlist log", log_info['backup_log']),
        ("No results log", log_info['no_results_log'])
    ]
    
    for name, filepath in files_to_check:
        from pathlib import Path
        path_obj = Path(filepath)
        exists = path_obj.exists()
        readable = exists and path_obj.is_file()
        size = path_obj.stat().st_size if exists else 0
        
        status = "✅" if exists else "❌"
        print(f"  {status} {name}:")
        print(f"     Path: {filepath}")
        print(f"     Exists: {exists}, Readable: {readable}, Size: {size} bytes")
    
    print(f"\n🔍 PlaylistLogger Test:")
    try:
        logger = PlaylistLogger()
        debug_info = logger.get_debug_info()
        print("✅ PlaylistLogger initialized successfully")
        for key, value in debug_info.items():
            print(f"     {key}: {value}")
    except Exception as e:
        print(f"❌ PlaylistLogger failed to initialize: {e}")
        import traceback
        traceback.print_exc()
