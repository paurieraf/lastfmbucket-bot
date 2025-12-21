"""
This module defines the service layer for handling business logic and view rendering.
"""

import datetime
import logging
from typing import Optional

import humanize
import pylast
import telegram
from emoji import emojize
from telegram import InlineKeyboardButton

import db
import lastfm
import responses
from lastfm import EntityType, LastfmClient, Period

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class LastfmService:
    """
    A service class to handle the business logic related to Last.fm.
    """

    STATUS_LIMIT = 5
    TOPS_DEFAULT_LIMIT = 10
    TOPS_EXTENDED_LIMIT = 50

    def __init__(self, lastfm_client: LastfmClient):
        self._lastfm_client = lastfm_client

    def set_lastfm_username(
        self, telegram_user_id: int, telegram_username: str, lastfm_username: str
    ) -> tuple[db.User | None, bool]:
        lastfm_user = self._lastfm_client.get_user(lastfm_username)
        if not lastfm_user:
            return None, False

        user = db.create_or_update_user(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            lastfm_username=lastfm_username,
        )
        return user, True

    def get_now_playing(
        self, telegram_user_id: int
    ) -> tuple[db.User | None, pylast.Track | None]:
        user = db.get_user(telegram_user_id)
        if not user:
            return None, None

        now_playing_track = self._lastfm_client.get_now_playing(user.lastfm_username)
        return user, now_playing_track

    def get_recent_tracks(
        self, telegram_user_id: int
    ) -> list[pylast.PlayedTrack] | None:
        user = db.get_user(telegram_user_id)
        if not user:
            return None

        recent_tracks = self._lastfm_client.get_recent_tracks(
            user.lastfm_username, limit=self.STATUS_LIMIT
        )
        return recent_tracks

    def get_tops(
        self,
        telegram_user_id: int,
        entity_type: EntityType,
        period: Period,
        extended_limit: bool = False,
    ) -> list[pylast.TopItem] | None:
        user = db.get_user(telegram_user_id)
        if not user:
            return None

        limit = (
            self.TOPS_DEFAULT_LIMIT if not extended_limit else self.TOPS_EXTENDED_LIMIT
        )
        if entity_type == EntityType.ARTIST:
            tops = self._lastfm_client.client.get_user(
                user.lastfm_username
            ).get_top_artists(period=period, limit=limit)
        elif entity_type == EntityType.ALBUM:
            tops = self._lastfm_client.client.get_user(
                user.lastfm_username
            ).get_top_albums(period=period, limit=limit)
        elif entity_type == EntityType.TRACK:
            tops = self._lastfm_client.client.get_user(
                user.lastfm_username
            ).get_top_tracks(period=period, limit=limit)
        else:
            tops = None
        return tops

    @staticmethod
    def unlink_user(telegram_user_id: int):
        db.delete_user(telegram_user_id)


class ViewService:
    """Returns a formatted response string for every command"""

    NOW_PLAYING_LESS_INFO = "now_playing_less_info"
    NOW_PLAYING_LESS_INFO_SHOW_COVER = "now_playing_less_info_show_cover"
    NOW_PLAYING_MORE_INFO = "now_playing_more_info"
    NOW_PLAYING_REFRESH = "now_playing_refresh"
    PREFERENCES_UNLINK_ACCOUNT = "preferences_unlink_account"

    TOPS_PREFIX = "tops_"

    def __init__(self, lastfm_service: LastfmService):
        self.lastfm_service = lastfm_service

    @staticmethod
    async def build_start_response(telegram_user: telegram.User) -> str:
        user = db.get_user(telegram_user.id)
        if not user:
            setup_lastfm_user_text = "Use /set [username] to set your Last.fm username."
        else:
            setup_lastfm_user_text = (
                f"Last.fm username already set to @{user.lastfm_username}"
            )

        response = responses.start_response.substitute(
            username=telegram_user.username, setup_lastfm_user=setup_lastfm_user_text
        )
        return emojize(response)

    async def build_np_response(
        self, telegram_user: telegram.User, show_cover: bool = False
    ) -> tuple[str, telegram.InlineKeyboardMarkup | None, str | None]:
        user, track = self.lastfm_service.get_now_playing(telegram_user.id)
        if not user:
            logging.warning(
                f"User {telegram_user.username} ({telegram_user.id}) not found in the database"
            )
            response = responses.user_not_found.substitute()
            return emojize(response), None, None

        if not track:
            response = responses.now_playing_no_currently_playing.substitute(
                lastfm_username=user.lastfm_username
            )
            return emojize(response), None, None

        response = responses.now_playing.substitute(
            lastfm_username=user.lastfm_username,
            track_artist=track.artist,
            track_url=track.get_url(),
            track_title=track.title,
            track_album=track.get_album().title,
        )
        keyboard = [
            [
                telegram.InlineKeyboardButton(
                    "More info", callback_data=self.NOW_PLAYING_MORE_INFO
                )
            ]
        ]
        if not show_cover:
            keyboard[0].insert(
                0,
                telegram.InlineKeyboardButton(
                    "🖼️", callback_data=self.NOW_PLAYING_LESS_INFO_SHOW_COVER
                ),
            )

        reply_markup = telegram.InlineKeyboardMarkup(keyboard)

        return (
            emojize(response),
            reply_markup,
            track.get_album().get_cover_image() if show_cover else None,
        )

    async def build_lastfm_username_set_response(
        self, telegram_user: telegram.User, lastfm_username: str
    ) -> str:
        user, lastfm_user_exists = self.lastfm_service.set_lastfm_username(
            telegram_user_id=telegram_user.id,
            telegram_username=telegram_user.username,
            lastfm_username=lastfm_username,
        )

        if not lastfm_user_exists:
            response = responses.lastfm_username_set_user_not_found.substitute(
                lastfm_username=lastfm_username
            )
            return emojize(response)

        response = responses.lastfm_username_set.substitute(
            lastfm_username=user.lastfm_username
        )
        return emojize(response)

    async def build_status_response(
        self, telegram_user: telegram.User, show_cover: bool = False
    ) -> tuple[str, telegram.InlineKeyboardMarkup | None, str | None]:
        recent_tracks = self.lastfm_service.get_recent_tracks(telegram_user.id)
        if not recent_tracks:
            response = responses.user_not_found.substitute()
            return emojize(response), None, None

        recent_tracks_template_list = ""

        for played_track in recent_tracks:
            time_ago = ""
            is_currently_playing = True
            if played_track.timestamp:
                is_currently_playing = False
                time_ago = (
                    f", {humanize.naturaldelta(datetime.datetime.now().timestamp() - float(played_track.timestamp))}"
                    f" ago"
                )

            recent_tracks_template_list += (
                f"{'⏳' if is_currently_playing else ''} 🎧<i>{played_track.track.artist.name}</i>"
                f" — <strong><a href='{played_track.track.get_url()}'>{played_track.track.title}</a></strong>,"
                f" [{played_track.album}]"
                f"{time_ago}"
                f"\n"
            )
        response = responses.recent_tracks.substitute(
            telegram_user_first_name=telegram_user.first_name,
            recent_tracks_list=recent_tracks_template_list,
        )
        keyboard = [
            [
                telegram.InlineKeyboardButton(
                    "Less info",
                    callback_data=self.NOW_PLAYING_LESS_INFO
                    if not show_cover
                    else self.NOW_PLAYING_LESS_INFO_SHOW_COVER,
                )
            ]
        ]
        if not show_cover:
            keyboard.insert(
                0,
                [
                    telegram.InlineKeyboardButton(
                        "🖼️", callback_data=self.NOW_PLAYING_MORE_INFO
                    )
                ],
            )
        reply_markup = telegram.InlineKeyboardMarkup(keyboard)
        last_played_track = recent_tracks[0].track
        last_played_track_album = last_played_track.get_album()
        return (
            emojize(response),
            reply_markup,
            last_played_track_album.get_cover_image()
            if last_played_track_album
            else None
            if show_cover
            else None,
        )

    async def build_tops_response(
        self,
        telegram_user_id: int,
        entity_type: Optional[lastfm.EntityType] = None,
        period: Optional[lastfm.Period] = None,
    ) -> tuple[str, telegram.InlineKeyboardMarkup]:
        if not entity_type:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "👤 Artist",
                        callback_data=f"{self.TOPS_PREFIX}{lastfm.EntityType.ARTIST}",
                    ),
                    InlineKeyboardButton(
                        "💿 Album",
                        callback_data=f"{self.TOPS_PREFIX}{lastfm.EntityType.ALBUM}",
                    ),
                    InlineKeyboardButton(
                        "🎵 Track",
                        callback_data=f"{self.TOPS_PREFIX}{lastfm.EntityType.TRACK}",
                    ),
                ]
            ]
            reply_markup = telegram.InlineKeyboardMarkup(keyboard)
            return emojize(
                responses.tops_choose_entity_type.substitute()
            ), reply_markup

        if not period:
            # Map periods to user-friendly names
            period_map = {
                lastfm.Period.WEEK: "1week",
                lastfm.Period.ONE_MONTH: "1month",
                lastfm.Period.THREE_MONTHS: "3month",
                lastfm.Period.SIX_MONTHS: "6month",
                lastfm.Period.YEAR: "1year",
                lastfm.Period.OVERALL: "alltime",
            }

            keyboard = []
            row = []
            for p, name in period_map.items():
                row.append(
                    InlineKeyboardButton(
                        name, callback_data=f"{self.TOPS_PREFIX}{entity_type}_{p}"
                    )
                )
                if len(row) == 3:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

            reply_markup = telegram.InlineKeyboardMarkup(keyboard)
            return emojize(
                responses.tops_choose_period.substitute(
                    entity_type=entity_type
                )
            ), reply_markup

        tops = self.lastfm_service.get_tops(telegram_user_id, entity_type, period)
        user = db.get_user(telegram_user_id)
        if not tops:
            return emojize(
                responses.tops_no_available_response.substitute(
                    lastfm_username=user.lastfm_username
                )
            ), None

        tops_list = ""
        for i, top in enumerate(tops, 1):
            if entity_type == EntityType.ARTIST:
                tops_list += f"{i}. <a href='{top.item.get_url()}'>{top.item.name}</a> - {top.weight} plays\n"
            else:
                tops_list += f"{i}. <a href='{top.item.get_url()}'>{top.item.title} — {top.item.artist}</a> - {top.weight} plays\n"

        # Map period back to user-friendly name for display
        period_display_map = {
            lastfm.Period.WEEK: "1week",
            lastfm.Period.ONE_MONTH: "1month",
            lastfm.Period.THREE_MONTHS: "3month",
            lastfm.Period.SIX_MONTHS: "6month",
            lastfm.Period.YEAR: "1year",
            lastfm.Period.OVERALL: "alltime",
        }
        period_name = period_display_map.get(period, period.name)

        response = responses.tops_list.substitute(
            entity_type=entity_type,
            period=period_name,
            tops_list=tops_list,
            lastfm_username=user.lastfm_username,
        )
        return emojize(response), None

    @staticmethod
    async def build_privacy_response() -> str:
        """Builds the privacy policy response."""
        return responses.privacy.substitute()

    async def build_preferences_response(
        self,
    ) -> tuple[str, telegram.InlineKeyboardMarkup]:
        """Builds the preferences response."""
        keyboard = [
            [
                telegram.InlineKeyboardButton(
                    "Unlink your account", callback_data=self.PREFERENCES_UNLINK_ACCOUNT
                )
            ]
        ]
        reply_markup = telegram.InlineKeyboardMarkup(keyboard)
        return emojize(responses.preferences.substitute()), reply_markup

    def build_preferences_unlink_account_response(self, telegram_user_id: int) -> str:
        """Builds the preferences unlink account response."""
        self.lastfm_service.unlink_user(telegram_user_id)
        return emojize(responses.preferences_unlink_account.substitute())
