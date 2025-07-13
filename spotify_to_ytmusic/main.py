import argparse
import importlib.metadata
import sys
from pathlib import Path

from spotify_to_ytmusic import controllers


class NewlineVersionAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        sys.stdout.write(
            f"spotify-to-ytmusic {importlib.metadata.version('spotify-to-ytmusic')}\n"
            f"ytmusicapi {importlib.metadata.version('ytmusicapi')} \n"
            f"spotipy {importlib.metadata.version('spotipy')}",
        )
        parser.exit()


def get_args(args=None):
    parser = argparse.ArgumentParser(
        description="Transfer spotify playlists to YouTube Music."
    )
    parser.add_argument(
        "-v",
        "--version",
        nargs=0,
        action=NewlineVersionAction,
    )
    subparsers = parser.add_subparsers(
        help="Provide a subcommand", dest="command", required=True
    )
    setup_parser = subparsers.add_parser("setup", help="Set up credentials")
    setup_parser.set_defaults(func=controllers.setup)
    setup_parser.add_argument(
        "--file", type=Path, help="Optional path to a settings.ini file"
    )

    cache_parser = argparse.ArgumentParser(add_help=False)
    cache_parser.add_argument(
        "--use-cached",
        action="store_true",
        default=False,
        help="(Optional) Enable the use of a cache file to save and retrieve query results.",
    )

    spotify_playlist = argparse.ArgumentParser(add_help=False)
    spotify_playlist.add_argument(
        "playlist", type=str, help="Provide a playlist Spotify link."
    )

    spotify_playlist_create = argparse.ArgumentParser(add_help=False)
    spotify_playlist_create.add_argument(
        "-d",
        "--date",
        action="store_true",
        help="Append the current date to the playlist name",
    )
    spotify_playlist_create.add_argument(
        "-i",
        "--info",
        type=str,
        help="Provide description information for the YouTube Music Playlist. Default: Spotify playlist description",
    )
    spotify_playlist_create.add_argument(
        "-n",
        "--name",
        type=str,
        help="Provide a name for the YouTube Music playlist. Default: Spotify playlist name",
    )
    spotify_playlist_create.add_argument(
        "-p",
        "--public",
        action="store_true",
        help="Make created playlist public. Default: private",
    )
    spotify_playlist_create.add_argument(
        "-l",
        "--like",
        action="store_true",
        help="Like the songs in the specified playlist",
    )

    create_parser = subparsers.add_parser(
        "create",
        help="Create a new playlist on YouTube Music.",
        parents=[spotify_playlist, spotify_playlist_create, cache_parser],
    )
    create_parser.set_defaults(func=controllers.create)

    liked_parser = subparsers.add_parser(
        "liked",
        help="Transfer all liked songs of the user.",
        parents=[spotify_playlist_create, cache_parser],
    )
    liked_parser.set_defaults(func=controllers.liked)

    update_parser = subparsers.add_parser(
        "update",
        help="Delete all entries in the provided Google Play Music playlist and "
        "update the playlist with entries from the Spotify playlist.",
        parents=[spotify_playlist, cache_parser],
    )
    update_parser.set_defaults(func=controllers.update)
    update_parser.add_argument(
        "name", type=str, help="The name of the YouTube Music playlist to update."
    )
    update_parser.add_argument(
        "--append", help="Do not delete items, append to target playlist instead"
    )

    update_all_parser = subparsers.add_parser(
        "update-all",
        help="Compare and update all saved playlists and albums between Spotify and YouTube Music.",
        parents=[cache_parser],
    )
    update_all_parser.set_defaults(func=controllers.update_all)
    update_all_parser.add_argument(
        "--target-user",
        type=str,
        help="Also include public playlists from this Spotify user ID",
    )
    update_all_parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of playlists to process before pausing (default: 5)",
    )
    update_all_parser.add_argument(
        "--batch-delay",
        type=int,
        default=2,
        help="Seconds to wait between batches (default: 2)",
    )
    update_all_parser.add_argument(
        "--append",
        action="store_true",
        help="Do not delete items, append missing songs to existing playlists instead"
    )
    update_all_parser.add_argument(
        "--tolerance",
        type=float,
        default=0.9,
        help="Minimum match ratio to consider playlist up-to-date (default: 0.9 = 90%%)"
    )


    remove_parser = subparsers.add_parser(
        "remove", help="Remove playlists with specified regex pattern."
    )
    remove_parser.set_defaults(func=controllers.remove)
    remove_parser.add_argument("pattern", help="regex pattern")

    all_parser = subparsers.add_parser(
        "all",
        help="Transfer all public playlists of the specified user (Spotify User ID).",
        parents=[cache_parser],
    )
    all_parser.add_argument(
        "user", type=str, help="Spotify userid of the specified user."
    )
    all_parser.set_defaults(func=controllers.all)
    all_parser.add_argument(
        "-l",
        "--like",
        action="store_true",
        help="Like the songs in all of the public playlist",
    )

    all_saved_parser = subparsers.add_parser(
        "all-saved",
        help="Transfer all saved content from your Spotify library (playlists and albums).",
        parents=[spotify_playlist_create, cache_parser],
    )
    all_saved_parser.set_defaults(func=controllers.all_saved)
    all_saved_parser.add_argument(
        "--target-user",
        type=str,
        help="Also include public playlists from this Spotify user ID",
    )
    all_saved_parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of playlists to process before pausing (default: 5)",
    )
    all_saved_parser.add_argument(
        "--batch-delay",
        type=int,
        default=2,
        help="Seconds to wait between batches (default: 2)",
    )

    all_sync_parser = subparsers.add_parser(
        "all-sync",
        help="Run all-saved and update-all commands every 15 minutes indefinitely until Enter is pressed.",
        parents=[spotify_playlist_create, cache_parser],
    )
    all_sync_parser.set_defaults(func=controllers.all_sync)
    all_sync_parser.add_argument(
        "--target-user",
        type=str,
        help="Also include public playlists from this Spotify user ID",
    )
    all_sync_parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of playlists to process before pausing (default: 5)",
    )
    all_sync_parser.add_argument(
        "--batch-delay",
        type=int,
        default=2,
        help="Seconds to wait between batches (default: 2)",
    )
    all_sync_parser.add_argument(
        "--append",
        action="store_true",
        help="Do not delete items, append missing songs to existing playlists instead"
    )
    all_sync_parser.add_argument(
        "--tolerance",
        type=float,
        default=0.9,
        help="Minimum match ratio to consider playlist up-to-date (default: 0.9 = 90%%)"
    )

    search_parser = subparsers.add_parser(
        "search",
        help="Search for a song on YouTube Music to cross-check the algorithm match result.",
        parents=[cache_parser],
    )
    search_parser.add_argument(
        "link", type=str, help="Link of the spotify song to search."
    )
    search_parser.set_defaults(func=controllers.search)

    cache_remove_parser = subparsers.add_parser("cache-clear", help="Clear cache file")
    cache_remove_parser.set_defaults(func=controllers.cache_clear)

    log_stats_parser = subparsers.add_parser(
        "log-stats", help="Show playlist operation logs and statistics"
    )
    log_stats_parser.set_defaults(func=controllers.log_stats)

    logs_location_parser = subparsers.add_parser(
        "logs-location", help="Show where log files and credentials are stored"
    )
    logs_location_parser.set_defaults(func=controllers.show_log_location)

    initial_setup_parser = subparsers.add_parser(
        "initial-setup",
        help="Scan existing YouTube Music playlists and populate logs for tracking",
        parents=[cache_parser],
    )
    initial_setup_parser.set_defaults(func=controllers.initial_setup)
    initial_setup_parser.add_argument(
        "--target-user",
        type=str,
        help="Also scan playlists that match public playlists from this Spotify user ID",
    )

    cache_migrate_parser = subparsers.add_parser(
        "cache-migrate", help="Manually check and migrate cache files from legacy locations"
    )
    cache_migrate_parser.set_defaults(func=controllers.cache_migrate)

    return parser.parse_args(args)


def main():
    args = get_args()
    args.func(args)


if __name__ == "__main__":
    main()
