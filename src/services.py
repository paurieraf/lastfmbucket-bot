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

import config
import db
import lastfm
import responses
from callbacks import Action, Callback, Entity, Period as CallbackPeriod, entity_from_lastfm, period_from_lastfm
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
    """Builds formatted responses and keyboards for bot commands."""

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
        self, telegram_user_id: int, show_cover: bool = False
    ) -> tuple[str, telegram.InlineKeyboardMarkup | None, str | None]:
        user, track = self.lastfm_service.get_now_playing(telegram_user_id)
        if not user:
            logging.warning(
                f"User with telegram_id {telegram_user_id} not found in the database"
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
                    "More info",
                    callback_data=Callback(Action.NP_MORE, telegram_user_id).encode(),
                )
            ]
        ]
        if not show_cover:
            keyboard[0].insert(
                0,
                telegram.InlineKeyboardButton(
                    "🖼️",
                    callback_data=Callback(Action.NP_LESS_COVER, telegram_user_id).encode(),
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
        self, telegram_user_id: int, show_cover: bool = False
    ) -> tuple[str, telegram.InlineKeyboardMarkup | None, str | None]:
        recent_tracks = self.lastfm_service.get_recent_tracks(telegram_user_id)
        user = db.get_user(telegram_user_id)
        if not recent_tracks or not user:
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
            telegram_user_first_name=user.telegram_username or user.lastfm_username,
            recent_tracks_list=recent_tracks_template_list,
        )
        less_info_action = Action.NP_LESS if not show_cover else Action.NP_LESS_COVER
        keyboard = [
            [
                telegram.InlineKeyboardButton(
                    "Less info",
                    callback_data=Callback(less_info_action, telegram_user_id).encode(),
                )
            ]
        ]
        if not show_cover:
            keyboard.insert(
                0,
                [
                    telegram.InlineKeyboardButton(
                        "🖼️",
                        callback_data=Callback(Action.NP_MORE, telegram_user_id).encode(),
                    )
                ],
            )
        reply_markup = telegram.InlineKeyboardMarkup(keyboard)
        last_played_track = recent_tracks[0].track

        cover_url = None
        if show_cover:
            try:
                last_played_track_album = last_played_track.get_album()
                if last_played_track_album:
                    cover_url = last_played_track_album.get_cover_image()
            except Exception:
                pass  # Track not found or no album info

        return emojize(response), reply_markup, cover_url

    async def build_tops_response(
        self,
        telegram_user_id: int,
        entity_type: Optional[lastfm.EntityType] = None,
        period: Optional[lastfm.Period] = None,
    ) -> tuple[str, telegram.InlineKeyboardMarkup | None]:
        if not entity_type:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "👤 Artist",
                        callback_data=Callback(
                            Action.TOPS, telegram_user_id, entity=Entity.ARTIST
                        ).encode(),
                    ),
                    InlineKeyboardButton(
                        "💿 Album",
                        callback_data=Callback(
                            Action.TOPS, telegram_user_id, entity=Entity.ALBUM
                        ).encode(),
                    ),
                    InlineKeyboardButton(
                        "🎵 Track",
                        callback_data=Callback(
                            Action.TOPS, telegram_user_id, entity=Entity.TRACK
                        ).encode(),
                    ),
                ]
            ]
            reply_markup = telegram.InlineKeyboardMarkup(keyboard)
            return emojize(
                responses.tops_choose_entity_type.substitute()
            ), reply_markup

        if not period:
            period_display = {
                CallbackPeriod.WEEK: "1week",
                CallbackPeriod.MONTH_1: "1month",
                CallbackPeriod.MONTH_3: "3month",
                CallbackPeriod.MONTH_6: "6month",
                CallbackPeriod.YEAR: "1year",
                CallbackPeriod.OVERALL: "alltime",
            }
            cb_entity = entity_from_lastfm(entity_type)

            keyboard = []
            row = []
            for cb_period, name in period_display.items():
                row.append(
                    InlineKeyboardButton(
                        name,
                        callback_data=Callback(
                            Action.TOPS, telegram_user_id, entity=cb_entity, period=cb_period
                        ).encode(),
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

    @staticmethod
    async def build_changelog_response() -> str:
        """Builds the changelog response by reading CHANGELOG.md."""
        try:
            changelog_content = config.CHANGELOG_PATH.read_text(encoding="utf-8")
            max_length = 4000
            if len(changelog_content) > max_length:
                changelog_content = changelog_content[:max_length] + "\n\n... (truncated)"
            return f"<pre>{changelog_content}</pre>"
        except FileNotFoundError:
            return "Changelog not available."

    async def build_preferences_response(
        self, telegram_user_id: int
    ) -> tuple[str, telegram.InlineKeyboardMarkup]:
        """Builds the preferences response."""
        keyboard = [
            [
                telegram.InlineKeyboardButton(
                    "Unlink your account",
                    callback_data=Callback(Action.PREF_UNLINK, telegram_user_id).encode(),
                )
            ]
        ]
        reply_markup = telegram.InlineKeyboardMarkup(keyboard)
        return emojize(responses.preferences.substitute()), reply_markup

    def build_preferences_unlink_account_response(self, telegram_user_id: int) -> str:
        """Builds the preferences unlink account response."""
        self.lastfm_service.unlink_user(telegram_user_id)
        return emojize(responses.preferences_unlink_account.substitute())

    async def build_compare_response(
        self, telegram_user_id: int, other_lastfm_username: str
    ) -> str:
        """Builds the compare response between two users."""
        user = db.get_user(telegram_user_id)
        if not user:
            return emojize(responses.compare_no_lastfm_set.substitute())

        my_stats = self.lastfm_service._lastfm_client.get_user_stats(user.lastfm_username)
        other_stats = self.lastfm_service._lastfm_client.get_user_stats(other_lastfm_username)

        if not my_stats:
            return emojize(
                responses.compare_user_not_found.substitute(username=user.lastfm_username)
            )
        if not other_stats:
            return emojize(
                responses.compare_user_not_found.substitute(username=other_lastfm_username)
            )

        common_artists = self.lastfm_service._lastfm_client.get_common_artists(
            user.lastfm_username, other_lastfm_username
        )

        if common_artists:
            common_artists_text = "\n".join(
                f"• {a['name']} ({a['plays1']:,} / {a['plays2']:,})"
                for a in common_artists
            )
        else:
            common_artists_text = "None found"

        top_artists1_text = ", ".join(
            f"{a['name']} ({a['plays']:,})" for a in my_stats["top_artists"][:3]
        )
        top_artists2_text = ", ".join(
            f"{a['name']} ({a['plays']:,})" for a in other_stats["top_artists"][:3]
        )

        response = responses.compare_stats.substitute(
            user1=my_stats["username"],
            user2=other_stats["username"],
            playcount1=f"{my_stats['playcount']:,}",
            playcount2=f"{other_stats['playcount']:,}",
            common_count=len(common_artists),
            common_artists=common_artists_text,
            top_artists1=top_artists1_text,
            top_artists2=top_artists2_text,
        )
        return emojize(response)
