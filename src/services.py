import asyncio
import datetime
import html
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from io import BytesIO
from typing import Callable, Optional

import humanize
import pylast
import telegram
from emoji import emojize
from telegram import InlineKeyboardButton
from lastfmcollagegenerator.collage_generator import CollageGenerator
from lastfmcollagegenerator.constants import (
    OVERLAY_BANNER,
    OVERLAY_STYLES,
    THEME_DARK,
    THEMES,
)
from lastfmcollagegenerator.effects import (
    DuotoneFilter,
    ImageFilter,
    VisualEffectPipeline,
)
from lastfmcollagegenerator.export import export_image
from lastfmcollagegenerator.fallback_art import FALLBACK_STYLE_GRADIENT, FALLBACK_STYLES
from lastfmcollagegenerator.presets import PRESET_NAMES, SOCIAL_PRESETS

import config
import db
import lastfm
import responses
from callbacks import (
    PRESET_ALIASES,
    Action,
    Callback,
    Entity,
    Period as CallbackPeriod,
    entity_from_lastfm,
)
from lastfm import EntityType, LastfmClient, Period

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

LASTFM_SEMAPHORE = asyncio.Semaphore(config.LASTFM_MAX_CONCURRENT)


async def _run_lastfm_call(func: Callable, *args, **kwargs):
    """Run a blocking Last.fm call off the event loop, bounded by a semaphore."""
    async with LASTFM_SEMAPHORE:
        return await asyncio.to_thread(func, *args, **kwargs)


class LastfmService:
    """
    A service class to handle the business logic related to Last.fm.
    """

    STATUS_LIMIT = 5
    TOPS_DEFAULT_LIMIT = 10
    TOPS_EXTENDED_LIMIT = 50

    def __init__(self, lastfm_client: LastfmClient):
        self._lastfm_client = lastfm_client

    async def set_lastfm_username(
        self, telegram_user_id: int, telegram_username: str, lastfm_username: str
    ) -> tuple[db.User | None, bool]:
        lastfm_user = await _run_lastfm_call(
            self._lastfm_client.get_user, lastfm_username
        )
        if not lastfm_user:
            return None, False

        user = db.create_or_update_user(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            lastfm_username=lastfm_username,
        )
        return user, True

    async def get_now_playing(
        self, telegram_user_id: int
    ) -> tuple[db.User | None, pylast.Track | None]:
        user = db.get_user(telegram_user_id)
        if not user:
            return None, None

        now_playing_track = await _run_lastfm_call(
            self._lastfm_client.get_now_playing, user.lastfm_username
        )
        return user, now_playing_track

    async def get_recent_tracks(
        self, telegram_user_id: int
    ) -> list[pylast.PlayedTrack] | None:
        user = db.get_user(telegram_user_id)
        if not user:
            return None

        recent_tracks = await _run_lastfm_call(
            self._lastfm_client.get_recent_tracks,
            user.lastfm_username,
            limit=self.STATUS_LIMIT,
        )
        return recent_tracks

    async def get_tops(
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
            tops = await _run_lastfm_call(
                self._lastfm_client.client.get_user(
                    user.lastfm_username
                ).get_top_artists,
                period=period,
                limit=limit,
            )
        elif entity_type == EntityType.ALBUM:
            tops = await _run_lastfm_call(
                self._lastfm_client.client.get_user(
                    user.lastfm_username
                ).get_top_albums,
                period=period,
                limit=limit,
            )
        elif entity_type == EntityType.TRACK:
            tops = await _run_lastfm_call(
                self._lastfm_client.client.get_user(
                    user.lastfm_username
                ).get_top_tracks,
                period=period,
                limit=limit,
            )
        else:
            tops = None
        return tops

    async def get_user_stats(self, username: str) -> dict | None:
        return await _run_lastfm_call(self._lastfm_client.get_user_stats, username)

    async def get_common_artists(
        self, username1: str, username2: str, limit: int = 50
    ) -> list[dict]:
        return await _run_lastfm_call(
            self._lastfm_client.get_common_artists, username1, username2, limit
        )

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
        user, track = await self.lastfm_service.get_now_playing(telegram_user_id)
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

        album = track.get_album()
        track_album = album.title if album else ""
        cover_image = album.get_cover_image() if (show_cover and album) else None

        response = responses.now_playing.substitute(
            lastfm_username=user.lastfm_username,
            track_artist=track.artist,
            track_url=track.get_url(),
            track_title=track.title,
            track_album=track_album,
        )
        keyboard = [
            [
                telegram.InlineKeyboardButton(
                    "More info",
                    callback_data=Callback(Action.NP_MORE, telegram_user_id).encode(),
                ),
                telegram.InlineKeyboardButton(
                    "👑 Qui ho coneix?",
                    callback_data=Callback(Action.WHOKNOWS, telegram_user_id).encode(),
                ),
            ]
        ]
        if not show_cover:
            keyboard[0].insert(
                0,
                telegram.InlineKeyboardButton(
                    "🖼️",
                    callback_data=Callback(
                        Action.NP_LESS_COVER, telegram_user_id
                    ).encode(),
                ),
            )

        reply_markup = telegram.InlineKeyboardMarkup(keyboard)

        return (
            emojize(response),
            reply_markup,
            cover_image,
        )

    async def build_lastfm_username_set_response(
        self, telegram_user: telegram.User, lastfm_username: str
    ) -> str:
        user, lastfm_user_exists = await self.lastfm_service.set_lastfm_username(
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
        recent_tracks = await self.lastfm_service.get_recent_tracks(telegram_user_id)
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
                        callback_data=Callback(
                            Action.NP_MORE, telegram_user_id
                        ).encode(),
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
            return emojize(responses.tops_choose_entity_type.substitute()), reply_markup

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
                            Action.TOPS,
                            telegram_user_id,
                            entity=cb_entity,
                            period=cb_period,
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
                responses.tops_choose_period.substitute(entity_type=entity_type)
            ), reply_markup

        tops = await self.lastfm_service.get_tops(telegram_user_id, entity_type, period)
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
                changelog_content = (
                    changelog_content[:max_length] + "\n\n... (truncated)"
                )
            return f"<pre>{changelog_content}</pre>"
        except FileNotFoundError:
            return "Changelog not available."

    async def build_preferences_response(
        self, telegram_user_id: int
    ) -> tuple[str, telegram.InlineKeyboardMarkup]:
        """Builds the preferences response."""
        user = db.get_user(telegram_user_id)
        opt_out = user.group_opt_out if user else False
        opt_out_btn_text = (
            "🔒 Ocultar-me de rànquings de grup"
            if not opt_out
            else "🔓 Mostrar-me a rànquings de grup"
        )
        keyboard = [
            [
                telegram.InlineKeyboardButton(
                    opt_out_btn_text,
                    callback_data=Callback(
                        Action.PREF_OPT_OUT, telegram_user_id
                    ).encode(),
                )
            ],
            [
                telegram.InlineKeyboardButton(
                    "Unlink your account",
                    callback_data=Callback(
                        Action.PREF_UNLINK, telegram_user_id
                    ).encode(),
                )
            ],
        ]
        reply_markup = telegram.InlineKeyboardMarkup(keyboard)
        return emojize(responses.preferences.substitute()), reply_markup

    def build_preferences_toggle_opt_out_response(
        self, telegram_user_id: int
    ) -> str:
        """Toggles user group ranking opt_out setting and returns feedback."""
        is_opted_out = db.toggle_user_group_opt_out(telegram_user_id)
        status_text = (
            "Ocult dels rànquings de grup 🔒"
            if is_opted_out
            else "Visible als rànquings de grup 🔓"
        )
        return emojize(
            responses.preferences_opt_out_updated.substitute(status=status_text)
        )

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

        my_stats, other_stats, common_artists = await asyncio.gather(
            self.lastfm_service.get_user_stats(user.lastfm_username),
            self.lastfm_service.get_user_stats(other_lastfm_username),
            self.lastfm_service.get_common_artists(
                user.lastfm_username, other_lastfm_username
            ),
        )

        if not my_stats:
            return emojize(
                responses.compare_user_not_found.substitute(
                    username=user.lastfm_username
                )
            )
        if not other_stats:
            return emojize(
                responses.compare_user_not_found.substitute(
                    username=other_lastfm_username
                )
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

    @staticmethod
    def build_collage_caption(
        entity_type: str,
        size: str,
        period: str,
        lastfm_username: str,
        tile_size: Optional[int] = None,
        theme: Optional[str] = None,
        overlay_style: Optional[str] = None,
        preset: Optional[str] = None,
        show_text: bool = True,
        font_bold: bool = False,
        filter_name: Optional[str] = None,
    ) -> str:
        """Builds the caption HTML string for a generated collage."""
        period_display_map = {
            "7day": "1 week",
            "1month": "1 month",
            "3month": "3 months",
            "6month": "6 months",
            "12month": "1 year",
            "overall": "all time",
        }
        period_label = period_display_map.get(period, period)
        tile_note = f", {tile_size}px tiles" if tile_size else ""
        if preset and preset in SOCIAL_PRESETS:
            sp = SOCIAL_PRESETS[preset]
            size_display = f"{preset} {sp.cols}x{sp.rows}"
        else:
            size_display = size

        style_parts: list[str] = []
        if theme and theme != "dark":
            style_parts.append(theme)
        if overlay_style and overlay_style != "banner":
            style_parts.append(overlay_style.replace("_", " "))
        if not show_text:
            style_parts.append("sense text")
        if font_bold:
            style_parts.append("bold")
        if filter_name:
            style_parts.append(f"filtre {filter_name}")
        style_note = f", {', '.join(style_parts)}" if style_parts else ""

        return responses.collage_caption.substitute(
            entity_type=entity_type.capitalize(),
            size=size_display,
            period=period_label,
            tile_note=tile_note,
            style_note=style_note,
            lastfm_username=lastfm_username,
        )

    async def build_collage_selection_response(
        self,
        telegram_user_id: int,
        entity: Optional[Entity] = None,
        size: Optional[str] = None,
        period: Optional[CallbackPeriod] = None,
        preset: Optional[str] = None,
        theme: Optional[str] = None,
        overlay: Optional[str] = None,
        style: Optional[str] = None,
    ) -> tuple[str, telegram.InlineKeyboardMarkup | None]:
        """
        Builds an interactive selection interface for collage parameters.
        Returns prompt message and InlineKeyboardMarkup.
        """
        if not entity:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "👤 Artist",
                        callback_data=Callback(
                            Action.COLLAGE, telegram_user_id, entity=Entity.ARTIST
                        ).encode(),
                    ),
                    InlineKeyboardButton(
                        "💿 Album",
                        callback_data=Callback(
                            Action.COLLAGE, telegram_user_id, entity=Entity.ALBUM
                        ).encode(),
                    ),
                    InlineKeyboardButton(
                        "🎵 Track",
                        callback_data=Callback(
                            Action.COLLAGE, telegram_user_id, entity=Entity.TRACK
                        ).encode(),
                    ),
                ]
            ]
            reply_markup = telegram.InlineKeyboardMarkup(keyboard)
            return emojize(
                responses.collage_choose_entity_type.substitute()
            ), reply_markup

        if not size and not preset:
            presets = [["3x3", "4x4", "5x5"], ["3x5", "10x5", "10x10"]]
            keyboard = [
                [
                    InlineKeyboardButton(
                        s,
                        callback_data=Callback(
                            Action.COLLAGE, telegram_user_id, entity=entity, size=s
                        ).encode(),
                    )
                    for s in row
                ]
                for row in presets
            ]
            social_presets = [
                ("story", "📱 Story"),
                ("post", "📸 Post"),
                ("header", "🖼️ Header"),
                ("wallpaper", "🖥️ Wallpaper"),
                ("4k", "🖥️ 4K"),
            ]
            keyboard.append(
                [
                    InlineKeyboardButton(
                        label,
                        callback_data=Callback(
                            Action.COLLAGE, telegram_user_id, entity=entity, preset=code
                        ).encode(),
                    )
                    for code, label in social_presets
                ]
            )
            entity_name = entity.name.lower()
            reply_markup = telegram.InlineKeyboardMarkup(keyboard)
            return (
                emojize(
                    responses.collage_choose_size.substitute(entity_type=entity_name)
                ),
                reply_markup,
            )

        if not period:
            period_display = {
                CallbackPeriod.WEEK: "1week",
                CallbackPeriod.MONTH_1: "1month",
                CallbackPeriod.MONTH_3: "3month",
                CallbackPeriod.MONTH_6: "6month",
                CallbackPeriod.YEAR: "1year",
                CallbackPeriod.OVERALL: "alltime",
            }
            keyboard = []
            row = []
            for cb_period, name in period_display.items():
                row.append(
                    InlineKeyboardButton(
                        name,
                        callback_data=Callback(
                            Action.COLLAGE,
                            telegram_user_id,
                            entity=entity,
                            size=size,
                            period=cb_period,
                            preset=preset,
                        ).encode(),
                    )
                )
                if len(row) == 3:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

            entity_name = entity.name.lower()
            size_label = PRESET_ALIASES.get(preset, preset) if preset else (size or "")
            reply_markup = telegram.InlineKeyboardMarkup(keyboard)
            return (
                emojize(
                    responses.collage_choose_period.substitute(
                        size=size_label, entity_type=entity_name
                    )
                ),
                reply_markup,
            )

        if style != "skip":
            theme_options = [
                ("dark", "Dark"),
                ("light", "Light"),
                ("glassmorphic", "Glass"),
                ("sunset", "Sunset"),
                ("neon", "Neon"),
            ]
            overlay_options = [
                ("banner", "Banner"),
                ("full_tint", "Full tint"),
                ("gradient", "Gradient"),
                ("pill", "Pill"),
                ("clean", "Clean"),
            ]
            keyboard = [
                [
                    InlineKeyboardButton(
                        label,
                        callback_data=Callback(
                            Action.COLLAGE,
                            telegram_user_id,
                            entity=entity,
                            size=size,
                            period=period,
                            preset=preset,
                            theme=code,
                            overlay=overlay,
                            style="set",
                        ).encode(),
                    )
                    for code, label in theme_options
                ],
                [
                    InlineKeyboardButton(
                        label,
                        callback_data=Callback(
                            Action.COLLAGE,
                            telegram_user_id,
                            entity=entity,
                            size=size,
                            period=period,
                            preset=preset,
                            theme=theme,
                            overlay=code,
                            style="set",
                        ).encode(),
                    )
                    for code, label in overlay_options
                ],
                [
                    InlineKeyboardButton(
                        "✨ Skip",
                        callback_data=Callback(
                            Action.COLLAGE,
                            telegram_user_id,
                            entity=entity,
                            size=size,
                            period=period,
                            preset=preset,
                            theme=theme,
                            overlay=overlay,
                            style="skip",
                        ).encode(),
                    )
                ],
            ]
            entity_name = entity.name.lower()
            size_label = PRESET_ALIASES.get(preset, preset) if preset else (size or "")
            current_style = " / ".join(
                filter(None, [theme or "dark", overlay or "banner"])
            )
            reply_markup = telegram.InlineKeyboardMarkup(keyboard)
            return (
                emojize(
                    responses.collage_choose_style.substitute(
                        size=size_label,
                        entity_type=entity_name,
                        current_style=f"Current: {current_style}",
                    )
                ),
                reply_markup,
            )

        return "", None


FILTER_ALIASES = {
    "duotone": "duotone",
    "bw": "bw",
    "blackwhite": "bw",
    "black_white": "bw",
    "grayscale": "bw",
    "greyscale": "bw",
    "sepia": "sepia",
    "cyberpunk": "cyberpunk",
    "sunset": "sunset",
    "matrix": "matrix",
}

FILTER_NAMES = (
    "duotone",
    "bw",
    "sepia",
    "cyberpunk",
    "sunset",
    "matrix",
)


def resolve_filter(
    filter_spec: Optional[str],
) -> Optional[ImageFilter | VisualEffectPipeline]:
    if not filter_spec:
        return None
    clean = filter_spec.strip().lower()
    if clean in ("duotone", "bw", "blackwhite", "black_white", "grayscale", "greyscale"):
        return DuotoneFilter()
    if clean == "sepia":
        return DuotoneFilter(black_color=(44, 28, 14), white_color=(240, 220, 180))
    if clean == "cyberpunk":
        return DuotoneFilter(black_color=(20, 0, 40), white_color=(0, 255, 255))
    if clean == "sunset":
        return DuotoneFilter(black_color=(40, 10, 30), white_color=(255, 120, 50))
    if clean == "matrix":
        return DuotoneFilter(black_color=(0, 20, 0), white_color=(50, 255, 50))
    if clean.startswith("duotone:") or clean.startswith("dt:"):
        payload = clean.split(":", 1)[1]
        parts = payload.split(",")
        if len(parts) == 2:
            return DuotoneFilter(black_color=parts[0].strip(), white_color=parts[1].strip())
    raise ValueError(
        f"Unknown filter: '{filter_spec}'. Supported options are: {', '.join(FILTER_NAMES)}, or duotone:<color1>,<color2>"
    )


@dataclass
class CollageOptions:
    """Render options for a collage generation.

    Mirrors the configurable subset of ``CollageGenerator.generate_async()``.
    """

    entity: str = "album"
    cols: int = 3
    rows: int = 3
    period: str = "7day"
    tile_size: Optional[int] = None
    theme: Optional[str] = None
    overlay_style: Optional[str] = None
    show_text: bool = True
    font_bold: bool = False
    preset: Optional[str] = None
    corner_radius: int = 0
    border_width: int = 0
    border_color: Optional[str] = None
    spacing: int = 0
    fallback_style: Optional[str] = None
    filter: Optional[str] = None

    def build_kwargs(self) -> dict:
        """Return kwargs for ``CollageGenerator.generate_async()``, omitting library defaults."""
        kwargs: dict = {}
        if self.theme is not None and self.theme != THEME_DARK:
            kwargs["theme"] = self.theme
        if self.overlay_style is not None and self.overlay_style != OVERLAY_BANNER:
            kwargs["overlay_style"] = self.overlay_style
        if not self.show_text:
            kwargs["show_text"] = False
        if self.font_bold:
            kwargs["font_bold"] = True
        if self.preset is not None:
            kwargs["preset"] = self.preset
        if self.corner_radius:
            kwargs["corner_radius"] = self.corner_radius
        if self.border_width:
            kwargs["border_width"] = self.border_width
        if self.border_color is not None:
            kwargs["border_color"] = self.border_color
        if self.spacing:
            kwargs["spacing"] = self.spacing
        if (
            self.fallback_style is not None
            and self.fallback_style != FALLBACK_STYLE_GRADIENT
        ):
            kwargs["fallback_style"] = self.fallback_style
        if self.filter is not None:
            resolved = resolve_filter(self.filter)
            if resolved is not None:
                kwargs["filters"] = resolved
        return kwargs


def parse_collage_args(args: list[str]) -> CollageOptions:
    """
    Parses CLI arguments for collage command.
    Returns a CollageOptions instance.
    """
    options = CollageOptions()

    max_cols = CollageGenerator.MAX_COLS
    max_rows = CollageGenerator.MAX_ROWS
    max_tiles = CollageGenerator.MAX_TILES
    min_tile = CollageGenerator.MIN_TILE_SIZE
    max_tile = CollageGenerator.MAX_TILE_SIZE

    entity_aliases = {
        "album": "album",
        "albums": "album",
        "alb": "album",
        "artist": "artist",
        "artists": "artist",
        "art": "artist",
        "track": "track",
        "tracks": "track",
        "song": "track",
        "songs": "track",
        "tra": "track",
    }
    period_aliases = {
        "7d": "7day",
        "7day": "7day",
        "7days": "7day",
        "week": "7day",
        "1w": "7day",
        "1week": "7day",
        "1m": "1month",
        "1month": "1month",
        "month": "1month",
        "3m": "3month",
        "3month": "3month",
        "3months": "3month",
        "6m": "6month",
        "6month": "6month",
        "6months": "6month",
        "1y": "12month",
        "1year": "12month",
        "12m": "12month",
        "12month": "12month",
        "year": "12month",
        "overall": "overall",
        "all": "overall",
        "alltime": "overall",
        "always": "overall",
    }
    theme_aliases = {
        "dark": "dark",
        "light": "light",
        "glass": "glassmorphic",
        "glassmorphic": "glassmorphic",
        "sunset": "sunset",
        "neon": "neon",
        "adaptive": "adaptive",
    }
    overlay_aliases = {
        "banner": "banner",
        "full_tint": "full_tint",
        "fulltint": "full_tint",
        "tint": "full_tint",
        "gradient": "gradient",
        "pill": "pill",
        "clean": "clean",
    }

    dim_pattern = re.compile(r"^(\d+)x(\d+)$", re.IGNORECASE)
    single_dim_pattern = re.compile(r"^(\d+)$")
    tile_size_pattern = re.compile(
        r"^(?:ts|tile|tilesize|tile_size|size)[:=](\d+)$", re.IGNORECASE
    )
    tile_size_px_pattern = re.compile(r"^(\d+)\s*px$", re.IGNORECASE)
    theme_pattern = re.compile(r"^(?:theme|tema)[:=](\w+)$", re.IGNORECASE)
    overlay_pattern = re.compile(r"^(?:overlay|ov|style)[:=](\w+)$", re.IGNORECASE)
    preset_pattern = re.compile(r"^preset[:=]([\w-]+)$", re.IGNORECASE)
    corner_pattern = re.compile(r"^(?:corner|radius)[:=](\d+)$", re.IGNORECASE)
    border_pattern = re.compile(r"^border[:=](\d+)$", re.IGNORECASE)
    border_color_pattern = re.compile(
        r"^(?:border_color|bc)[:=](#?[0-9a-fA-F]{6})$", re.IGNORECASE
    )
    spacing_pattern = re.compile(r"^(?:spacing|gap)[:=](\d+)$", re.IGNORECASE)
    fallback_pattern = re.compile(r"^fallback[:=](\w+)$", re.IGNORECASE)
    filter_pattern = re.compile(r"^(?:filter|fx)[:=]([\w:,#\(\)-]+)$", re.IGNORECASE)

    usage = (
        "Usage: /collage [size: 3x3|10x10] [period: week|1m|overall] "
        "[entity: album|artist|track] [tile_size: 150px] "
        "[theme: dark|light|glassmorphic|sunset|neon|adaptive] "
        "[overlay: banner|full_tint|gradient|pill|clean] "
        "[preset: story|post|header|wallpaper|4k] [notext] [bold] "
        "[filter: duotone|bw|sepia|cyberpunk|sunset|matrix] "
        "[corner: n] [border: n] [border_color: #hex] [spacing: n] "
        "[fallback: gradient|black]"
    )

    for arg in args:
        clean = arg.strip().lower()
        if not clean:
            continue
        if clean in entity_aliases:
            options.entity = entity_aliases[clean]
        elif clean in period_aliases:
            options.period = period_aliases[clean]
        elif clean == "notext":
            options.show_text = False
        elif clean == "bold":
            options.font_bold = True
        elif clean in PRESET_ALIASES:
            options.preset = PRESET_ALIASES[clean]
        elif m := theme_pattern.match(clean):
            key = m.group(1).lower()
            if key not in theme_aliases or theme_aliases[key] not in THEMES:
                raise ValueError(f"Unknown theme: '{key}'. Options are: {THEMES}")
            options.theme = theme_aliases[key]
        elif m := overlay_pattern.match(clean):
            key = m.group(1).lower()
            if key not in overlay_aliases or overlay_aliases[key] not in OVERLAY_STYLES:
                raise ValueError(
                    f"Unknown overlay style: '{key}'. Options are: {OVERLAY_STYLES}"
                )
            options.overlay_style = overlay_aliases[key]
        elif m := preset_pattern.match(clean):
            key = m.group(1).lower()
            preset = PRESET_ALIASES.get(key, key)
            if preset not in PRESET_NAMES:
                raise ValueError(
                    f"Unknown preset: '{key}'. Options are: {PRESET_NAMES} "
                    f"(short: {tuple(PRESET_ALIASES)})"
                )
            options.preset = preset
        elif m := fallback_pattern.match(clean):
            key = m.group(1).lower()
            if key not in FALLBACK_STYLES:
                raise ValueError(
                    f"Unknown fallback style: '{key}'. Options are: {FALLBACK_STYLES}"
                )
            options.fallback_style = key
        elif m := filter_pattern.match(clean):
            f_val = m.group(1).lower()
            resolve_filter(f_val)
            options.filter = f_val
        elif m := corner_pattern.match(clean):
            options.corner_radius = int(m.group(1))
        elif m := border_pattern.match(clean):
            options.border_width = int(m.group(1))
        elif m := border_color_pattern.match(arg.strip()):
            color = m.group(1)
            options.border_color = color if color.startswith("#") else f"#{color}"
        elif m := spacing_pattern.match(clean):
            options.spacing = int(m.group(1))
        elif m := tile_size_pattern.match(clean):
            ts = int(m.group(1))
            if not (min_tile <= ts <= max_tile):
                raise ValueError(
                    f"Tile size must be between {min_tile} and {max_tile} pixels, got {ts}"
                )
            options.tile_size = ts
        elif m := tile_size_px_pattern.match(clean):
            ts = int(m.group(1))
            if not (min_tile <= ts <= max_tile):
                raise ValueError(
                    f"Tile size must be between {min_tile} and {max_tile} pixels, got {ts}"
                )
            options.tile_size = ts
        elif m := dim_pattern.match(clean):
            c, r = int(m.group(1)), int(m.group(2))
            if not (1 <= c <= max_cols and 1 <= r <= max_rows):
                raise ValueError(
                    f"Collage dimensions must be between 1x1 and {max_cols}x{max_rows}, got {c}x{r}"
                )
            if (c * r) > max_tiles:
                raise ValueError(
                    f"Total tile count ({c * r}) exceeds maximum capacity of {max_tiles} tiles."
                )
            options.cols, options.rows = c, r
        elif m := single_dim_pattern.match(clean):
            d = int(m.group(1))
            if not (1 <= d <= max_cols):
                raise ValueError(
                    f"Collage dimension must be between 1 and {max_cols}, got {d}"
                )
            if (d * d) > max_tiles:
                raise ValueError(
                    f"Total tile count ({d * d}) exceeds maximum capacity of {max_tiles} tiles."
                )
            options.cols, options.rows = d, d
        else:
            raise ValueError(f"Unrecognized parameter: '{arg}'. {usage}")

    for name, value in (
        ("corner_radius", options.corner_radius),
        ("border_width", options.border_width),
        ("spacing", options.spacing),
    ):
        if value < 0:
            raise ValueError(f"{name} must be a non-negative integer, got {value}")

    return options


class CollageService:
    """
    A service class to handle collage generation using lastfmcollagegenerator.
    """

    DEFAULT_CACHE_DIR = config.PROJECT_ROOT / "data" / "collage_cache"

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        cache_dir: str | None = None,
    ):
        key = api_key or config.LASTFM_API_KEY or ""
        secret = api_secret or config.LASTFM_API_SECRET or ""
        cache_dir = cache_dir or str(self.DEFAULT_CACHE_DIR)
        os.makedirs(cache_dir, exist_ok=True)
        self._cache_dir = cache_dir
        self._generator = CollageGenerator(lastfm_api_key=key, lastfm_api_secret=secret)

    async def generate_collage_image(
        self, username: str, options: CollageOptions, export_format: str = "WEBP"
    ) -> BytesIO:
        """
        Generates a collage image asynchronously via generate_async and returns a BytesIO stream.
        """
        image = await self._generator.generate_async(
            entity=options.entity,
            username=username,
            cols=options.cols,
            rows=options.rows,
            period=options.period,
            tile_size=options.tile_size,
            cache_dir=self._cache_dir,
            **options.build_kwargs(),
        )
        ext = export_format.lower()
        if ext == "jpg":
            ext = "jpeg"
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            export_image(image, tmp_path, format=export_format)
            with open(tmp_path, "rb") as f:
                bio = BytesIO(f.read())
            bio.name = f"collage.{ext}"
            bio.seek(0)
            return bio
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


class GroupService:
    """
    A service class to handle group music intelligence, WhoKnows rankings, and Crowns.
    """

    def __init__(self, lastfm_client: LastfmClient):
        self._lastfm_client = lastfm_client

    async def get_whoknows(
        self, chat_id: int, chat_name: str, artist_query: str
    ) -> tuple[str, bool]:
        """
        Executes WhoKnows query for a specific artist in a chat.
        Returns (html_response_message, is_success).
        """
        # 1. Canonicalize artist with Last.fm
        artist_info = await _run_lastfm_call(
            self._lastfm_client.get_artist_canonical_info, artist_query
        )
        if not artist_info:
            return responses.whoknows_artist_not_found.substitute(
                artist_name=html.escape(artist_query)
            ), False

        canonical_name, artist_url = artist_info

        # 2. Get active linked chat members (excluding opt_out)
        members = await asyncio.to_thread(db.get_linked_chat_members, chat_id)
        if not members:
            return responses.whoknows_no_members.substitute(
                chat_name=html.escape(chat_name or "this chat")
            ), False

        # 3. Query playcounts in parallel
        async def _fetch_user_plays(user: db.User) -> tuple[db.User, int]:
            plays = await _run_lastfm_call(
                self._lastfm_client.get_user_artist_playcount,
                user.lastfm_username,
                canonical_name,
            )
            return user, plays

        tasks = [_fetch_user_plays(m) for m in members]
        user_plays_results = await asyncio.gather(*tasks)

        # 4. Filter > 0 plays and sort descending
        active_listeners = [
            (u, plays) for u, plays in user_plays_results if plays > 0
        ]
        active_listeners.sort(key=lambda x: x[1], reverse=True)

        if not active_listeners:
            return responses.whoknows_no_listeners.substitute(
                artist_name=html.escape(canonical_name),
                artist_url=artist_url,
                chat_name=html.escape(chat_name or "this chat"),
            ), True

        # 5. Check and update Crown
        top_user, top_plays = active_listeners[0]
        curr_crown, prev_crown = await asyncio.to_thread(
            db.upsert_crown,
            chat_id=chat_id,
            artist_name=canonical_name,
            artist_url=artist_url,
            user=top_user,
            playcount=top_plays,
        )

        dethroned_banner = ""
        if prev_crown and prev_crown.user.telegram_id != top_user.telegram_id:
            prev_name = prev_crown.user.telegram_username or f"User {prev_crown.user.telegram_id}"
            new_name = top_user.telegram_username or f"User {top_user.telegram_id}"
            dethroned_banner = (
                f"\n\n⚔️ <b>NOU REI DE LA BANDA!</b> 👑\n"
                f"<b>@{new_name}</b> ({top_plays:,} plays) ha destronat a <b>@{prev_name}</b> ({prev_crown.playcount:,} plays)!"
            )

        # 6. Format ranking list
        total_plays = sum(p for _, p in active_listeners)
        rank_badges = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        ranking_lines = []
        for i, (u, plays) in enumerate(active_listeners[:15], start=1):
            badge = rank_badges[i - 1] if i <= len(rank_badges) else f"{i}."
            crown_icon = " 👑" if i == 1 else ""
            uname = f"@{u.telegram_username}" if u.telegram_username else f"User {u.telegram_id}"
            pct = (plays / total_plays * 100) if total_plays > 0 else 0
            ranking_lines.append(
                f"{badge} <b>{uname}</b> — <b>{plays:,}</b> plays{crown_icon} ({pct:.0f}%)"
            )

        ranking_list = "\n".join(ranking_lines)

        response_html = responses.whoknows_ranking.substitute(
            artist_name=html.escape(canonical_name),
            artist_url=artist_url,
            chat_name=html.escape(chat_name or "this chat"),
            dethroned_banner=dethroned_banner,
            ranking_list=ranking_list,
            total_plays=f"{total_plays:,}",
            listeners_count=len(active_listeners),
        )
        return emojize(response_html), True

    async def get_crowns_hall_of_fame(self, chat_id: int, chat_name: str) -> str:
        """
        Retrieves the crowns leaderboard for a chat.
        """
        leaderboard = await asyncio.to_thread(db.get_chat_crowns_leaderboard, chat_id)
        if not leaderboard:
            return emojize(
                responses.crowns_no_crowns.substitute(
                    chat_name=html.escape(chat_name or "this chat")
                )
            )

        rank_badges = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        lines = []
        for i, entry in enumerate(leaderboard, start=1):
            badge = rank_badges[i - 1] if i <= len(rank_badges) else f"{i}."
            user = entry["user"]
            count = entry["crown_count"]
            uname = f"@{user.telegram_username}" if user.telegram_username else f"User {user.telegram_id}"
            samples = entry["samples"]
            sample_str = ", ".join(
                f"<a href='{s['url']}'>{html.escape(s['name'])}</a> ({s['plays']:,})"
                if s["url"] else f"{html.escape(s['name'])} ({s['plays']:,})"
                for s in samples
            )
            samples_formatted = f" — <i>{sample_str}</i>" if sample_str else ""
            lines.append(f"{badge} <b>{uname}:</b> {count} 👑{samples_formatted}")

        return emojize(
            responses.crowns_leaderboard.substitute(
                chat_name=html.escape(chat_name or "this chat"),
                leaderboard_list="\n".join(lines),
            )
        )

    async def get_user_crowns_showcase(
        self, chat_id: int, chat_name: str, target_user: db.User
    ) -> str:
        """
        Retrieves all crowns held by a specific user in a chat.
        """
        crowns = await asyncio.to_thread(db.get_user_crowns, chat_id, target_user.telegram_id)
        display_name = f"@{target_user.telegram_username}" if target_user.telegram_username else f"User {target_user.telegram_id}"

        if not crowns:
            return emojize(
                responses.user_no_crowns.substitute(
                    display_name=display_name,
                    chat_name=html.escape(chat_name or "this chat"),
                )
            )

        lines = []
        for c in crowns:
            artist_link = (
                f"<a href='{c.artist_url}'>{html.escape(c.artist_name)}</a>"
                if c.artist_url
                else html.escape(c.artist_name)
            )
            lines.append(f"👑 {artist_link} — <b>{c.playcount:,}</b> scrobbles")

        return emojize(
            responses.user_crowns_list.substitute(
                display_name=display_name,
                chat_name=html.escape(chat_name or "this chat"),
                crown_count=len(crowns),
                crowns_list="\n".join(lines),
            )
        )

