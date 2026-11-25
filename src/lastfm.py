import logging
from enum import StrEnum

import pylast
from pylast import LastFMNetwork, PlayedTrack, Track, User

import config

logger = logging.getLogger(__name__)


def compute_common_artists(
    artists1: list[dict], artists2: list[dict], limit: int = 10
) -> list[dict]:
    """Compute common artists between two top-artist lists in memory."""
    user2_by_key: dict[str, int] = {}
    for artist in artists2:
        key = artist["name"].lower()
        if key not in user2_by_key:
            user2_by_key[key] = int(artist["plays"])

    common: list[dict] = []
    seen: set[str] = set()
    for artist in artists1:
        key = artist["name"].lower()
        if key in user2_by_key and key not in seen:
            seen.add(key)
            common.append(
                {
                    "name": artist["name"],
                    "plays1": int(artist["plays"]),
                    "plays2": user2_by_key[key],
                }
            )
            if len(common) >= limit:
                break
    return common


class Period(StrEnum):
    OVERALL = pylast.PERIOD_OVERALL
    WEEK = pylast.PERIOD_7DAYS
    ONE_MONTH = pylast.PERIOD_1MONTH
    THREE_MONTHS = pylast.PERIOD_3MONTHS
    SIX_MONTHS = pylast.PERIOD_6MONTHS
    YEAR = pylast.PERIOD_12MONTHS


class EntityType(StrEnum):
    ARTIST = "artist"
    ALBUM = "album"
    TRACK = "track"


class LastfmClient:
    def __init__(self):
        self.client = LastFMNetwork(
            api_key=config.LASTFM_API_KEY, api_secret=config.LASTFM_API_SECRET
        )

    def get_user(self, username: str) -> User | None:
        clean_username = (username or "").strip()
        if not clean_username:
            return None
        try:
            user = self.client.get_user(clean_username)
            user.get_registered()
            return user
        except pylast.WSError as e:
            logger.info(f"Last.fm user '{clean_username}' not found: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to validate Last.fm user '{clean_username}': {e}")
            return None

    def get_now_playing(self, username: str) -> Track | None:
        clean_username = (username or "").strip()
        if not clean_username:
            return None
        now_playing = self.client.get_user(clean_username).get_now_playing()
        return now_playing

    def get_recent_tracks(self, username: str, limit: int = 10) -> list[PlayedTrack]:
        clean_username = (username or "").strip()
        if not clean_username:
            return []
        recent_tracks = self.client.get_user(clean_username).get_recent_tracks(
            now_playing=True, limit=limit
        )
        return recent_tracks

    def get_artist_canonical_info(self, artist_name: str) -> tuple[str, str] | None:
        """
        Validates an artist with Last.fm and retrieves canonical name and web URL.
        Returns (canonical_name, url) or None if artist not found.
        """
        import urllib.parse

        clean_name = (artist_name or "").strip()
        if not clean_name:
            return None

        try:
            artist = self.client.get_artist(clean_name)
            canonical_name = artist.get_name(properly_capitalized=True)
            if not canonical_name:
                return None
            try:
                url = artist.get_url()
            except Exception:
                url = f"https://www.last.fm/music/{urllib.parse.quote_plus(canonical_name)}"
            return canonical_name, url
        except pylast.WSError as e:
            logger.warning(f"Last.fm artist '{clean_name}' not found: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to resolve artist '{clean_name}': {e}")
            return None

    def get_user_artist_playcount(self, username: str, artist_name: str) -> int:
        """
        Retrieves total scrobbles for a specific artist by a specific Last.fm user.
        """
        try:
            artist = pylast.Artist(
                artist_name, self.client, username=username.strip()
            )
            count = artist.get_userplaycount()
            return int(count) if count is not None else 0
        except Exception as e:
            logger.debug(f"Error fetching playcount for {username} - {artist_name}: {e}")
            return 0

    def get_user_playcount(self, username: str) -> int | None:
        """Get total scrobble count for a Last.fm user."""
        clean_username = (username or "").strip()
        if not clean_username:
            return None
        try:
            playcount = self.client.get_user(clean_username).get_playcount()
            return int(playcount) if playcount is not None else 0
        except Exception as e:
            logger.error(f"Error getting playcount for {clean_username}: {e}")
            return None

    def get_user_top_artists(
        self, username: str, period: Period = Period.OVERALL, limit: int = 50
    ) -> list[dict] | None:
        """Get top artists for a Last.fm user as [{'name': str, 'plays': int}, ...]."""
        clean_username = (username or "").strip()
        if not clean_username:
            return None
        try:
            top_artists = self.client.get_user(clean_username).get_top_artists(
                period=period, limit=limit
            )
            return [
                {"name": item.item.name, "plays": int(item.weight)}
                for item in top_artists
            ]
        except Exception as e:
            logger.error(f"Error getting top artists for {clean_username}: {e}")
            return None

    def get_user_stats(self, username: str) -> dict | None:
        """Get comprehensive stats for a user."""
        try:
            user = self.client.get_user(username)
            playcount = user.get_playcount()
            top_artists = user.get_top_artists(period=Period.OVERALL, limit=5)
            top_albums = user.get_top_albums(period=Period.OVERALL, limit=5)
            top_tracks = user.get_top_tracks(period=Period.OVERALL, limit=5)

            return {
                "username": username,
                "playcount": playcount,
                "top_artists": [
                    {"name": item.item.name, "plays": int(item.weight)}
                    for item in top_artists
                ],
                "top_albums": [f"{item.item.artist} - {item.item.title}" for item in top_albums],
                "top_tracks": [f"{item.item.artist} - {item.item.title}" for item in top_tracks],
            }
        except Exception as e:
            logger.error(f"Error getting stats for {username}: {e}")
            return None

    def get_common_artists(
        self, username1: str, username2: str, limit: int = 50
    ) -> list[dict]:
        """Find common artists between two users based on their top artists."""
        artists1 = self.get_user_top_artists(
            username1, period=Period.OVERALL, limit=limit
        )
        artists2 = self.get_user_top_artists(
            username2, period=Period.OVERALL, limit=limit
        )
        if artists1 is None or artists2 is None:
            return []
        return compute_common_artists(artists1, artists2, limit=10)
