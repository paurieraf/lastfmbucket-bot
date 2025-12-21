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
