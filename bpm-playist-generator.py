#!/usr/bin/env python3
import argparse
import json
import os

import spotipy
from spotipy.oauth2 import SpotifyImplicitGrant

scope = "user-library-read,playlist-read-private,playlist-modify-private"
sp = spotipy.Spotify(auth_manager=SpotifyImplicitGrant(scope=scope))
current_user = sp.current_user()
album_cache = {}
playlist_cache = {}
track_cache = {}


def get_all_user_tracks_from_albums(
    force_update_album_tracks=False, force_update_audio_features=False
):
    current_offset = 0
    result_items = None
    limit = 50

    while result_items is None or len(result_items) == limit:
        results = sp.current_user_saved_albums(limit=limit, offset=current_offset)
        result_items = results["items"]
        print(f"got {len(result_items)} albums. offset={current_offset}")
        for item in result_items:
            tracks = get_enriched_album_tracks(
                item["album"],
                force_update_album_tracks,
                force_update_audio_features,
            )
            for track in tracks:
                track_cache[track["id"]] = track

        current_offset += limit


def get_all_user_tracks_from_playlists(
    force_update_playlist_tracks=False, force_update_audio_features=False
):
    current_offset = 0
    result_items = None
    limit = 50

    while result_items is None or len(result_items) == limit:
        results = sp.current_user_playlists(limit=limit, offset=current_offset)
        result_items = results["items"]
        print(f"got {len(result_items)} playlists. offset={current_offset}")
        for playlist in result_items:
            if current_user["id"] == playlist["owner"]["id"]:
                tracks = get_enriched_playlist_tracks(
                    playlist,
                    force_update_playlist_tracks,
                    force_update_audio_features,
                )
                for track in tracks:
                    track_cache[track["id"]] = track
        current_offset += limit


def get_enriched_playlist_tracks(
    playlist, force_update_playlist_tracks=False, force_update_audio_features=False
):
    tracks = []
    playlist_id = playlist["id"]
    filename = f"cache/playlist/{playlist_id}"
    # check if file exists in cache directory
    if not force_update_playlist_tracks and playlist_id in playlist_cache:
        print(f"found cached tracks for playlist {playlist['name']} in memory cache")
        return playlist_cache[filename]

    playlist_tracks = []
    offset = 0
    limit = 50
    while True:
        print(f"getting tracks for playlist {playlist['name']} with offset {offset}...")
        playlist_tracks_result = sp.playlist_tracks(
            playlist_id, limit=limit, offset=offset
        )
        if len(playlist_tracks_result["items"]) == 0:
            break
        playlist_tracks.extend(playlist_tracks_result["items"])
        offset += limit

    for track_wrapper in playlist_tracks:
        full_track = track_wrapper["track"]
        track_id = full_track["id"]
        if track_id is None:
            print(f"track {full_track['name']} has no id, skipping...")
            continue  # skip tracks without an ID

        if not force_update_playlist_tracks and track_id in track_cache:
            tracks.append(track_cache[track_id])
            continue

        if force_update_audio_features or track_id not in track_cache:
            print(
                f"getting features for track {track_id} - {full_track['name']} on {playlist['name']}..."
            )
            features_result = sp.audio_features(track_id)
        else:
            features_result = track_cache[track_id]["features"]

        bpm = float("nan")
        if len(features_result) > 0 and features_result[0] is not None:
            bpm = features_result[0]["tempo"]
        else:
            print(f"no features found for track {track_id}. result: {features_result}")

        tracks.append(
            {
                "id": full_track["id"],
                "name": full_track["name"],
                "duration_ms": full_track["duration_ms"],
                "explicit": full_track["explicit"],
                "track_number": full_track["track_number"],
                "artist": full_track["artists"][0]["name"],
                "album": full_track["album"]["name"],
                "playlist": playlist["name"],
                "bpm": bpm,
                "features": features_result,
            }
        )
    # save tracks to a json file
    with open(filename, "w") as f:
        json.dump(tracks, f, indent=2)
    playlist_cache[playlist_id] = tracks
    return tracks


def get_enriched_album_tracks(
    album, force_update_album_tracks=False, force_update_audio_features=False
):
    tracks = []
    album_id = album["id"]
    filename = f"cache/album/{album_id}"
    # check if file exists in cache directory
    if not force_update_album_tracks and album_id in album_cache:
        print(f"found cached tracks for album {album['name']} in memory cache")
        return album_cache[album_id]

    full_tracks = album["tracks"]["items"]
    if len(full_tracks) != album["total_tracks"]:
        print(
            f"album {album['name']} has {len(full_tracks)} tracks, but total tracks is {album['total_tracks']}. "
        )
        while full_tracks != album["total_tracks"]:
            print(f"getting tracks for album {album['name']}...")
            album_tracks_result = sp.album_tracks(
                album_id, limit=50, offset=len(full_tracks)
            )
            if len(album_tracks_result["items"]) == 0:
                break
            full_tracks.extend(album_tracks_result["items"])

    for full_track in full_tracks:
        track_id = full_track["id"]
        if force_update_audio_features or track_id not in track_cache:
            print(
                f"getting features for track {track_id} - {full_track['name']} on {album['name']}..."
            )
            features_result = sp.audio_features(track_id)
        else:
            features_result = track_cache[track_id]["features"]

        bpm = float("nan")
        if len(features_result) > 0 and features_result[0] is not None:
            bpm = features_result[0]["tempo"]
        else:
            print(f"no features found for track {track_id}. result: {features_result}")

        tracks.append(
            {
                "id": full_track["id"],
                "name": full_track["name"],
                "duration_ms": full_track["duration_ms"],
                "explicit": full_track["explicit"],
                "track_number": full_track["track_number"],
                "artist": album["artists"][0]["name"],
                "album": album["name"],
                "bpm": bpm,
                "features": features_result,
            }
        )
    # save tracks to a json file
    with open(filename, "w") as f:
        json.dump(tracks, f, indent=2)
    album_cache[album_id] = tracks
    return tracks


def load_album_cache():
    # for each file in the cache directory, load the json file and add it to the track_cache
    for filename in os.listdir("cache/album"):
        with open(f"cache/album/{filename}", "r") as f:
            tracks = json.load(f)
            album_cache[filename] = tracks
            for track in tracks:
                track_cache[track["id"]] = track
    print(f"loaded {len(album_cache)} albums from cache")


def load_playlist_cache():
    for filename in os.listdir("cache/playlist"):
        with open(f"cache/playlist/{filename}", "r") as f:
            tracks = json.load(f)
            playlist_cache[filename] = tracks
            for track in tracks:
                track_cache[track["id"]] = track
    print(f"loaded {len(playlist_cache)} playlists from cache")


def load_caches():
    load_album_cache()
    load_playlist_cache()
    if len(album_cache) == 0:
        print("No album cache found, loading from Spotify...")
        get_all_user_tracks_from_albums()
    if len(playlist_cache) == 0:
        print("No playlist cache found, loading from Spotify...")
        get_all_user_tracks_from_playlists()


# Update the saved data in the disk cache
# with potentially new attributes like 'duration_ms' or 'popularity'
def update_saved_data(args):
    if args.force_update_audio_features:
        print("Forcing update of audio features for all tracks...")
        return
    get_all_user_tracks_from_albums(True, args.force_update_audio_features)
    get_all_user_tracks_from_playlists(True, args.force_update_audio_features)


def is_track_within_bpm_range(track, bpm_min, bpm_max):
    # also consider if double the bpm is within the range
    # if bpm is NaN, return False
    if track.get("duration_ms", 0) < 1000 * 60 * 1.5:
        return False
    bpm = track["bpm"]
    if bpm is None or bpm < 0:
        return False

    if bpm_min <= bpm <= bpm_max:
        return True
    if bpm_min <= bpm * 2 <= bpm_max:
        features = track["features"][0] if track["features"] else {}
        if features:
            energy, danceability, loudness = (
                features.get("energy", "N/A"),
                features.get("danceability", "N/A"),
                features.get("loudness", "N/A"),
            )
            if energy > 0.3 and loudness > -12 and danceability > 0.5:
                return True


def print_tracks(args):
    print("Name|Artist|Album|BPM|Energy|Danceability|Loudness")
    for track in track_cache.values():
        if is_track_within_bpm_range(track, args.bpm_min, args.bpm_max):
            energy = track["features"][0]["energy"] if track["features"] else "N/A"
            danceability = (
                track["features"][0]["danceability"] if track["features"] else "N/A"
            )
            loudness = track["features"][0]["loudness"] if track["features"] else "N/A"
            if "|" in track["name"]:
                track["name"] = track["name"].replace("|", "")
            print(
                f"{track['name']}|{track['artist']}|{track['album']}|{track['bpm']}|{energy}|{danceability}|{loudness}"
            )
            # print(
            #         f"{track['name']} - artist: {track['artist']} - album: {track['album']} - {track['bpm']} BPM - energy: {energy} - danceability: {danceability} - loudness: {loudness}"
            # )


def create_playlist(args):
    # This function would create a playlist using the Spotify API
    # For now, we will just print the tracks that would be added to the playlist

    filtered_tracks = [
        t
        for t in track_cache.values()
        if is_track_within_bpm_range(t, args.bpm_min, args.bpm_max)
    ]
    print(f"Creating playlist '{args.name}' with {len(filtered_tracks)} tracks")
    for track in filtered_tracks:
        print(f"{track['name']} by {track['artist']} - {track['bpm']} BPM")

    playlist = sp.user_playlist_create(current_user["id"], args.name, public=False)
    # add 100 tracks at a time due to Spotify API limitations
    for i in range(0, len(filtered_tracks), 100):
        batch = filtered_tracks[i : i + 100]
        print(f"Adding {len(batch)} tracks to playlist {args.name}")
        sp.playlist_add_items(
            playlist["id"],
            [
                f"spotify:track:{track['id']}"
                for track in batch
                if track["id"] is not None
            ],
        )


def main():
    # arg parser with options 'create-playlist', 'print' with option 'bpm-min' and 'bpm-max'

    parser = argparse.ArgumentParser(description="BPM Playlist Generator")
    parser.add_argument("--bpm-min", type=float, default=160, help="Minimum BPM")
    parser.add_argument("--bpm-max", type=float, default=180, help="Maximum BPM")

    subparsers = parser.add_subparsers(dest="command")
    # create-playlist command
    create_playlist_parser = subparsers.add_parser(
        "create-playlist", help="Create a BPM playlist"
    )
    create_playlist_parser.add_argument(
        "--name", type=str, help="Name of the playlist to create", required=True
    )
    create_playlist_parser.set_defaults(func=create_playlist)

    # print command
    print_parser = subparsers.add_parser("print", help="Print album cache")
    print_parser.set_defaults(func=print_tracks)

    # update command
    update_parser = subparsers.add_parser(
        "update-cache", help="Update the saved data in the disk cache"
    )
    update_parser.add_argument(
        "--force-update-audio-features",
        action="store_true",
        help="Force update audio features for all tracks",
    )
    update_parser.set_defaults(func=update_saved_data)

    load_caches()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
