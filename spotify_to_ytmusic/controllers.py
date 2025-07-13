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
    log_info = get_log_files_info()
    print("\nLog files and credentials are stored in:")
    print(f"Cache directory: {log_info['cache_directory']}")
    print(f"- Settings file: {log_info['settings_file']}")
    print(f"- Spotify cache: {log_info['spotify_cache']}")
    print(f"- Playlist operations log: {log_info['backup_log']}")
    print(f"- No results log: {log_info['no_results_log']}")


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
    logger = PlaylistLogger()
    print(f"Operation logged to: {logger.get_log_location()}")


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
    logger = PlaylistLogger()
    
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
    logger = PlaylistLogger()
    
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
            logger.log_playlist_operation(
                operation_type="all-saved",
                spotify_playlist_name=p["name"],
                youtube_playlist_name=playlist_name,
                tracks=playlist.get("tracks", []),
                success=False,
                tracks_found=0,
                tracks_total=len(playlist.get("tracks", []))
            )
            print(f"Could not transfer {content_type.lower()} '{playlist_name}'. {ex!s}")
    
    print(f"\nTransfer completed: {transferred} transferred, {skipped} skipped")


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
    logger = PlaylistLogger()
    
    if not isinstance(spotify.api.auth_manager, spotipy.SpotifyOAuth):
        raise Exception("OAuth not configured, please run setup and set OAuth to 'yes'")
    
    # Collect all playlists from different sources (same logic as all_saved)
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
    
    print(f"Total: {len(all_playlists)} playlists to analyze. Starting comparison...")
    
    count = 1
    updated = 0
    skipped = 0
    not_found = 0
    
    for i, p in enumerate(all_playlists):
        # Batch processing with delays
        if i > 0 and i % args.batch_size == 0:
            print(f"Processed {i} playlists. Waiting {args.batch_delay} seconds...")
            time.sleep(args.batch_delay)
        
        owner_name = p['owner']['display_name'] if 'owner' in p else 'Unknown'
        playlist_name = p["name"]
        content_type = "Album" if p.get("type") == "album" else "Playlist"
        
        print(f"\n{content_type} {count}: '{playlist_name}' (by {owner_name})")
        count += 1
        
        # Check if playlist exists in YouTube Music
        existing_playlist = ytmusic.get_existing_playlist_by_name(playlist_name)
        if not existing_playlist:
            print(f"  Not found in YouTube Music - SKIPPED")
            not_found += 1
            continue
        
        print(f"  Found in YouTube Music as: '{existing_playlist['title']}'")
        
        try:
            # Get Spotify tracks
            if p.get("type") == "album":
                spotify_tracks = p["tracks"]
            else:
                spotify_playlist = spotify.getSpotifyPlaylist(p["external_urls"]["spotify"])
                spotify_tracks = spotify_playlist["tracks"]
            
            # Get YouTube Music tracks for size comparison
            youtube_tracks = ytmusic.get_playlist_tracks(existing_playlist["id"])
            
            # Check if playlist is up to date based on logs (fast check with size comparison)
            log_status = logger.is_playlist_up_to_date(
                p["name"], 
                spotify_tracks, 
                existing_playlist["title"], 
                len(youtube_tracks)
            )
            
            if log_status and log_status.get("up_to_date"):
                print(f"  📋 Log shows up-to-date (last updated: {log_status['last_updated'][:10]}) - SKIPPED")
                skipped += 1
                continue
            elif log_status and log_status.get("size_changed"):
                print(f"  📋 Size change detected: {log_status.get('reason', 'Unknown')}")
            elif log_status and log_status.get("hash_changed"):
                print(f"  📋 Content change detected (last updated: {log_status['last_updated'][:10]})")
            else:
                print(f"  📋 No log history found, performing full comparison")
            
            print(f"  Spotify: {len(spotify_tracks)} tracks, YouTube: {len(youtube_tracks)} tracks")
            
            # First, determine which Spotify tracks are actually available in YouTube Music
            print(f"  🔍 Checking track availability...")
            available_spotify_tracks = []
            videoIds = ytmusic.search_songs(spotify_tracks, use_cached=args.use_cached)
            
            # Map successful matches back to original tracks
            for idx, spotify_track in enumerate(spotify_tracks):
                if idx < len(videoIds) and videoIds[idx]:  # videoIds[idx] is not None/empty
                    available_spotify_tracks.append(spotify_track)
            
            print(f"  📊 Available tracks - Spotify: {len(available_spotify_tracks)}, YouTube: {len(youtube_tracks)}")
            
            # Compare only available tracks
            tracks_match = True
            significant_difference = False
            
            # If YouTube has significantly fewer tracks than what's available from Spotify,
            # or more tracks, then it needs updating
            availability_ratio = len(youtube_tracks) / len(available_spotify_tracks) if len(available_spotify_tracks) > 0 else 0
            
            if availability_ratio < 0.95 or availability_ratio > 1.05:  # More than 5% difference
                significant_difference = True
                print(f"  ⚠️  Significant track count difference: {availability_ratio:.2%} ratio")
            
            # Check track order for available songs (compare first N tracks where N = min length)
            if not significant_difference:
                comparison_length = min(len(available_spotify_tracks), len(youtube_tracks))
                order_matches = 0
                
                for idx in range(comparison_length):
                    if idx < len(available_spotify_tracks) and idx < len(youtube_tracks):
                        spotify_track = available_spotify_tracks[idx]
                        youtube_track = youtube_tracks[idx]
                        if ytmusic.compare_track_similarity(spotify_track, youtube_track):
                            order_matches += 1
                        else:
                            print(f"  🔄 Track {idx+1} differs: '{spotify_track['name']}' vs '{youtube_track['title']}'")
                
                # Consider tracks matching if at least the specified tolerance of compared tracks match in order
                match_ratio = order_matches / comparison_length if comparison_length > 0 else 1
                tracks_match = match_ratio >= args.tolerance
                
                print(f"  📈 Track order match: {order_matches}/{comparison_length} ({match_ratio:.1%}) - Tolerance: {args.tolerance:.1%}")
            else:
                tracks_match = False
            
            if tracks_match and not significant_difference:
                print(f"  ✅ Tracks match sufficiently (considering availability) - SKIPPED")
                skipped += 1
                continue
            
            # Update playlist if tracks don't match significantly
            print(f"  🔄 Updating playlist...")
            
            if not args.append:
                ytmusic.remove_songs(existing_playlist["id"])
                time.sleep(2)
            
            ytmusic.add_playlist_items(existing_playlist["id"], videoIds)
            
            # Log the successful update
            logger.log_playlist_operation(
                operation_type="update-all",
                spotify_playlist_name=p["name"],
                youtube_playlist_name=existing_playlist["title"],
                tracks=spotify_tracks,
                youtube_playlist_id=existing_playlist["id"],
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
                spotify_playlist_name=p["name"],
                youtube_playlist_name=existing_playlist.get("title", playlist_name) if 'existing_playlist' in locals() else playlist_name,
                tracks=spotify_tracks if 'spotify_tracks' in locals() else [],
                success=False,
                tracks_found=0,
                tracks_total=len(spotify_tracks) if 'spotify_tracks' in locals() else 0
            )
            print(f"  ❌ Could not update: {ex!s}")
    
    print(f"\nUpdate completed: {updated} updated, {skipped} already up-to-date, {not_found} not found in YouTube Music")


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


def initial_setup(args):
    """Scan existing YouTube Music playlists and populate logs for future tracking"""
    spotify, ytmusic = _init()
    logger = PlaylistLogger()
    
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
    Run all-saved and update-all commands every 15 minutes indefinitely until Enter is pressed.
    """
    print("🔄 Starting all-sync mode...")
    print("This will run 'all-saved' followed by 'update-all' every 15 minutes.")
    print("Press Enter at any time to stop the sync process.\n")
    
    # Event to signal when to stop
    stop_event = threading.Event()
    
    def input_listener():
        """Listen for Enter key press in a separate thread"""
        input("Press Enter to stop the sync process...\n")
        stop_event.set()
    
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
            stop_event.set()
        except Exception as ex:
            print(f"\n❌ Error during sync cycle: {ex}")
            print("Will retry in next cycle...")
    
    # Start input listener thread
    input_thread = threading.Thread(target=input_listener, daemon=True)
    input_thread.start()
    
    cycle_count = 0
    try:
        while not stop_event.is_set():
            cycle_count += 1
            print(f"\n📊 === Sync Cycle #{cycle_count} ===")
            
            run_sync_cycle()
            
            if stop_event.is_set():
                break
                
            # Wait 15 minutes or until stop signal
            print(f"\n⏰ Waiting 15 minutes until next sync cycle...")
            print(f"Next sync at: {datetime.fromtimestamp(time.time() + 900).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Wait in small increments to check for stop signal
            for _ in range(900):  # 900 seconds = 15 minutes
                if stop_event.is_set():
                    break
                time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n⏹️  Sync process interrupted")
    
    finally:
        print(f"\n🏁 All-sync stopped after {cycle_count} cycle(s)")
        print("Thank you for using spotify-to-ytmusic!")
