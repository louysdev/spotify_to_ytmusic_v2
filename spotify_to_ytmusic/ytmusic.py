import re
from collections import OrderedDict
from pathlib import Path

from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth import OAuthCredentials

from spotify_to_ytmusic.settings import Settings, NO_RESULTS_LOG_FILE
from spotify_to_ytmusic.utils.cache_manager import CacheManager
from spotify_to_ytmusic.utils.match import get_best_fit_song_id

cacheManager = CacheManager()


class YTMusicTransfer:
    def __init__(self):
        settings = Settings()
        headers = settings["youtube"]["headers"]
        assert headers.startswith("{"), "ytmusicapi headers not set or invalid"
        oauth_credentials = (
            None
            if settings["youtube"]["auth_type"] != "oauth"
            else OAuthCredentials(
                client_id=settings["youtube"]["client_id"],
                client_secret=settings["youtube"]["client_secret"],
            )
        )
        self.api = YTMusic(
            headers, settings["youtube"]["user_id"], oauth_credentials=oauth_credentials
        )

    def create_playlist(self, name, info, privacy="PRIVATE", tracks=None):
        return self.api.create_playlist(name, info, privacy, video_ids=tracks)

    def rate_song(self, id, rating):
        return self.api.rate_song(id, rating)

    def search_songs(self, tracks, use_cached: bool = False):
        videoIds = []
        songs = list(tracks)
        notFound = list()
        lookup_ids = cacheManager.load_lookup_table()

        if use_cached:
            print("Use of cache file is enabled.")

        print("Searching YouTube...")
        for i, song in enumerate(songs):
            name = re.sub(r" \(feat.*\..+\)", "", song["name"])
            query = song["artist"] + " " + name
            query = query.replace(" &", "")

            if use_cached and query in lookup_ids.keys():
                videoIds.append(lookup_ids[query])
                continue

            result = self.api.search(query)

            if len(result) == 0:
                notFound.append(query)
            else:
                targetSong = get_best_fit_song_id(result, song)
                if targetSong is None:
                    notFound.append(query)
                else:
                    videoIds.append(targetSong)
                    if use_cached:
                        lookup_ids[query] = targetSong
                        cacheManager.save_to_lookup_table(lookup_ids)

            if i > 0 and i % 10 == 0:
                print(f"YouTube tracks: {i}/{len(songs)}")

        with open(NO_RESULTS_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(notFound))
            f.write("\n")
            f.close()

        return videoIds

    def add_playlist_items(self, playlistId, videoIds):
        videoIds = OrderedDict.fromkeys(videoIds)
        self.api.add_playlist_items(playlistId, videoIds)

    def get_playlist_id(self, name):
        pl = self.api.get_library_playlists(10000)
        try:
            playlist = next(x for x in pl if x["title"].find(name) != -1)["playlistId"]
            return playlist
        except StopIteration:
            raise Exception("Playlist title not found in playlists")

    def playlist_exists(self, name):
        """Check if a playlist with similar name already exists (matching at least 2 words)"""
        try:
            pl = self.api.get_library_playlists(10000)
            
            # Clean and split the target name into words
            target_words = set(re.sub(r'[^\w\s]', '', name.lower()).split())
            
            for playlist in pl:
                existing_title = playlist["title"]
                # Clean and split existing playlist name into words
                existing_words = set(re.sub(r'[^\w\s]', '', existing_title.lower()).split())
                
                # Count common words (excluding very common words)
                common_words = target_words.intersection(existing_words)
                # Filter out very short words (1-2 characters) as they're often not meaningful
                meaningful_common = [word for word in common_words if len(word) > 2]
                
                # Consider it a match if:
                # 1. Exact match (original behavior)
                # 2. At least 2 meaningful words in common
                # 3. At least 70% of words match for shorter titles
                if (existing_title.lower() == name.lower() or 
                    len(meaningful_common) >= 2 or
                    (len(target_words) <= 3 and len(common_words) >= max(2, len(target_words) * 0.7))):
                    return existing_title  # Return the existing title for logging
                    
            return False
        except Exception:
            return False

    def get_playlist_tracks(self, playlist_id):
        """Get tracks from an existing YouTube Music playlist"""
        try:
            playlist_data = self.api.get_playlist(playlist_id, 5000)
            tracks = []
            if "tracks" in playlist_data:
                for track in playlist_data["tracks"]:
                    if track and "title" in track:
                        # Extract artist and title from YouTube Music track
                        title = track["title"]
                        artists = []
                        if "artists" in track and track["artists"]:
                            artists = [artist["name"] for artist in track["artists"] if artist and "name" in artist]
                        
                        tracks.append({
                            "title": title,
                            "artists": artists,
                            "duration": track.get("duration_seconds", 0),
                            "videoId": track.get("videoId", "")
                        })
            return tracks
        except Exception:
            return []

    def get_existing_playlist_by_name(self, name):
        """Get playlist ID and basic info by similar name matching"""
        try:
            pl = self.api.get_library_playlists(10000)
            
            # Use the same logic as playlist_exists but return full info
            target_words = set(re.sub(r'[^\w\s]', '', name.lower()).split())
            
            for playlist in pl:
                existing_title = playlist["title"]
                existing_words = set(re.sub(r'[^\w\s]', '', existing_title.lower()).split())
                
                common_words = target_words.intersection(existing_words)
                meaningful_common = [word for word in common_words if len(word) > 2]
                
                if (existing_title.lower() == name.lower() or 
                    len(meaningful_common) >= 2 or
                    (len(target_words) <= 3 and len(common_words) >= max(2, len(target_words) * 0.7))):
                    return {
                        "id": playlist["playlistId"],
                        "title": existing_title,
                        "trackCount": playlist.get("count", 0)
                    }
                    
            return None
        except Exception:
            return None

    def compare_track_similarity(self, spotify_track, youtube_track):
        """Compare if two tracks are similar based on title and artist matching"""
        # Clean track names
        spotify_title = re.sub(r'[^\w\s]', '', spotify_track["name"].lower()).split()
        youtube_title = re.sub(r'[^\w\s]', '', youtube_track["title"].lower()).split()
        
        # Artist comparison
        spotify_artist = spotify_track["artist"].lower()
        youtube_artists = " ".join(youtube_track["artists"]).lower() if youtube_track["artists"] else ""
        
        # Title similarity (at least 2 words in common)
        title_common = set(spotify_title).intersection(set(youtube_title))
        meaningful_title_common = [word for word in title_common if len(word) > 2]
        
        # Artist similarity
        artist_words_spotify = set(re.sub(r'[^\w\s]', '', spotify_artist).split())
        artist_words_youtube = set(re.sub(r'[^\w\s]', '', youtube_artists).split())
        artist_common = artist_words_spotify.intersection(artist_words_youtube)
        meaningful_artist_common = [word for word in artist_common if len(word) > 2]
        
        # Consider it a match if:
        # 1. At least 2 meaningful words match in title AND at least 1 artist word matches
        # 2. Title is very similar (70%+ words) AND artist matches
        title_match = len(meaningful_title_common) >= 2
        artist_match = len(meaningful_artist_common) >= 1
        
        return title_match and artist_match

    def remove_songs(self, playlistId):
        items = self.api.get_playlist(playlistId, 10000)
        if "tracks" in items:
            self.api.remove_playlist_items(playlistId, items["tracks"])

    def remove_playlists(self, pattern):
        playlists = self.api.get_library_playlists(10000)
        p = re.compile(f"{pattern}")
        matches = [pl for pl in playlists if p.match(pl["title"])]
        print("The following playlists will be removed:")
        print("\n".join([pl["title"] for pl in matches]))
        print("Please confirm (y/n):")

        choice = input().lower()
        if choice[:1] == "y":
            [self.api.delete_playlist(pl["playlistId"]) for pl in matches]
            print(str(len(matches)) + " playlists deleted.")
        else:
            print("Aborted. No playlists were deleted.")
