import logging
from enum import StrEnum

import pylast
from pylast import LastFMNetwork, PlayedTrack, Track, User

import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


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
        user = self.client.get_user(username)
        return user

    def get_now_playing(self, username: str) -> Track | None:
        now_playing = self.client.get_user(username).get_now_playing()
        return now_playing

    def get_recent_tracks(self, username: str, limit=int) -> list[PlayedTrack]:
        recent_tracks = self.client.get_user(username).get_recent_tracks(
            now_playing=True, limit=limit
        )
        return recent_tracks

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
        try:
            user1_artists = {
                item.item.name.lower(): {"name": item.item.name, "plays": int(item.weight)}
                for item in self.client.get_user(username1).get_top_artists(
                    period=Period.OVERALL, limit=limit
                )
            }
            user2_artists = {
                item.item.name.lower(): int(item.weight)
                for item in self.client.get_user(username2).get_top_artists(
                    period=Period.OVERALL, limit=limit
                )
            }
            common = [
                {
                    "name": user1_artists[name]["name"],
                    "plays1": user1_artists[name]["plays"],
                    "plays2": user2_artists[name],
                }
                for name in user1_artists
                if name in user2_artists
            ]
            return common[:10]  # Return top 10 common artists
        except Exception as e:
            logger.error(f"Error getting common artists: {e}")
            return []
