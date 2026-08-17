"""
Telegram bot command handlers.

This module contains handlers for commands and callback queries.
"""

import asyncio
import functools
import html
import logging
from typing import Callable, Optional

import telegram.constants
from dotenv import load_dotenv
from emoji import emojize
from telegram import BotCommand, Update
from telegram.ext import ContextTypes

import ai
import db
import lastfm
import responses
from callbacks import Action, Callback
from services import (
    CollageOptions,
    CollageService,
    GroupService,
    LastfmService,
    ViewService,
    parse_collage_args,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

COLLAGE_SEMAPHORE = asyncio.Semaphore(2)


def log_command(command_name: str) -> Callable:
    """Decorator to log command executions to the database."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
        ):
            user = update.effective_user
            chat = update.effective_chat
            if user:
                db.log_command(
                    user_id=user.id,
                    username=user.username or "",
                    command=command_name,
                    args=" ".join(context.args) if context.args else "",
                    chat_id=chat.id if chat else 0,
                    chat_type=chat.type if chat else "",
                    chat_name=(chat.title or chat.username or "") if chat else "",
                )
            return await func(update, context, *args, **kwargs)

        return wrapper

    return decorator


# Command constants
START_COMMAND = "start"
STATUS_COMMAND = "status"
NOW_PLAYING_COMMAND = "np"
TOPS_COMMAND = "tops"
COLLAGE_COMMAND = "collage"
PREFERENCES_COMMAND = "preferences"
HELP_COMMAND = "help"
CHANGELOG_COMMAND = "changelog"
SET_COMMAND = "set"
PRIVACY_COMMAND = "privacy"
COMPARE_COMMAND = "compare"
VIBE_COMMAND = "vibe"
ROAST_COMMAND = "roast"
RECOMMEND_COMMAND = "recommend"
WHOKNOWS_COMMAND = "whoknows"
WK_ALIAS = "wk"
CROWNS_COMMAND = "crowns"
MYCROWNS_ALIAS = "mycrowns"

# Public bot commands registered with Telegram UI
BOT_COMMANDS: list[BotCommand] = [
    BotCommand(NOW_PLAYING_COMMAND, "Show currently playing track"),
    BotCommand(STATUS_COMMAND, "Show recent scrobbles"),
    BotCommand(TOPS_COMMAND, "Show top artists, albums, or tracks"),
    BotCommand(COLLAGE_COMMAND, "Generate visual collage of your top items"),
    BotCommand(WHOKNOWS_COMMAND, "Show who in this chat listens to an artist"),
    BotCommand(CROWNS_COMMAND, "Show group crowns hall of fame or user crowns"),
    BotCommand(SET_COMMAND, "Link your Last.fm username"),
    BotCommand(COMPARE_COMMAND, "Compare listening stats with another user"),
    BotCommand(VIBE_COMMAND, "AI analysis of your current vibe"),
    BotCommand(ROAST_COMMAND, "AI roast of your music taste"),
    BotCommand(RECOMMEND_COMMAND, "AI-powered music recommendations"),
    BotCommand(PREFERENCES_COMMAND, "Manage bot preferences"),
    BotCommand(HELP_COMMAND, "Show bot help and description"),
    BotCommand(CHANGELOG_COMMAND, "Show recent bot changelog"),
    BotCommand(PRIVACY_COMMAND, "Show privacy policy"),
]


async def _handle_np_less(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cb: Callback
) -> None:
    await now_playing(update, context, telegram_user_id=cb.owner_id)


async def _handle_np_less_cover(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cb: Callback
) -> None:
    await now_playing(update, context, show_cover=True, telegram_user_id=cb.owner_id)


async def _handle_np_more(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cb: Callback
) -> None:
    await status(update, context, show_cover=True, telegram_user_id=cb.owner_id)


async def _handle_pref_unlink(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cb: Callback
) -> None:
    await unlink_account(update, context, telegram_user_id=cb.owner_id)


async def _handle_tops(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cb: Callback
) -> None:
    entity_type = cb.to_lastfm_entity()
    period = cb.to_lastfm_period()
    await tops(
        update,
        context,
        telegram_user_id=cb.owner_id,
        entity_type=entity_type,
        period=period,
    )


async def _edit_message_text(
    query: telegram.CallbackQuery,
    text: str,
    reply_markup: telegram.InlineKeyboardMarkup | None = None,
) -> None:
    """Edit a message, tolerating Telegram's 'Message is not modified' error."""
    try:
        if reply_markup:
            await query.edit_message_text(text=text, reply_markup=reply_markup)
        else:
            await query.edit_message_text(text=text)
    except telegram.error.BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def _handle_collage(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cb: Callback
) -> None:
    query = update.callback_query
    if not query:
        return

    user_id = cb.owner_id
    view_service: ViewService = context.bot_data["view_service"]
    collage_service: CollageService = context.bot_data["collage_service"]

    # If style step was confirmed (Skip), generate collage
    if cb.entity and (cb.size or cb.preset) and cb.period and cb.style == "skip":
        user = db.get_user(user_id)
        if not user:
            await query.edit_message_text(
                emojize(responses.user_not_found.substitute())
            )
            return

        entity_str = cb.to_collage_entity_str()
        period_str = cb.to_collage_period_str()
        preset_str = cb.to_collage_preset_str()
        try:
            cols, rows = map(int, (cb.size or "3x3").lower().split("x"))
        except Exception:
            cols, rows = 3, 3
        size_str = preset_str or cb.size or "3x3"

        await query.edit_message_text(
            f"🎨 Generating your {size_str} {entity_str} collage..."
        )
        if update.effective_chat:
            try:
                await context.bot.send_chat_action(
                    chat_id=update.effective_chat.id,
                    action=telegram.constants.ChatAction.UPLOAD_PHOTO,
                )
            except Exception:
                pass

        options = CollageOptions(
            entity=entity_str,
            cols=cols,
            rows=rows,
            period=period_str,
            preset=preset_str,
            theme=cb.theme,
            overlay_style=cb.overlay,
        )
        try:
            async with COLLAGE_SEMAPHORE:
                bio = await collage_service.generate_collage_image(
                    username=user.lastfm_username, options=options
                )
            caption = view_service.build_collage_caption(
                entity_type=entity_str,
                size=size_str,
                period=period_str,
                lastfm_username=user.lastfm_username,
                theme=cb.theme,
                overlay_style=cb.overlay,
                preset=preset_str,
            )
            if query.message:
                await query.message.reply_photo(photo=bio, caption=caption)
        except Exception as e:
            logger.exception(f"Error generating collage: {e}")
            if query.message:
                await query.message.reply_text(
                    emojize(responses.collage_error.substitute(error=str(e)))
                )
        return

    # Otherwise show next step in interactive selection
    response, reply_markup = await view_service.build_collage_selection_response(
        user_id,
        entity=cb.entity,
        size=cb.size,
        period=cb.period,
        preset=cb.preset,
        theme=cb.theme,
        overlay=cb.overlay,
        style=cb.style,
    )
    if reply_markup or response:
        await _edit_message_text(query, response, reply_markup)


async def _handle_pref_opt_out(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cb: Callback
) -> None:
    query = update.callback_query
    if not query:
        return
    view_service: ViewService = context.bot_data["view_service"]
    msg = view_service.build_preferences_toggle_opt_out_response(cb.owner_id)
    text, reply_markup = await view_service.build_preferences_response(cb.owner_id)
    await _edit_message_text(query, text=f"{text}\n\n{msg}", reply_markup=reply_markup)


async def _handle_whoknows_button(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cb: Callback
) -> None:
    query = update.callback_query
    if not query or not update.effective_chat:
        return
    lastfm_service: LastfmService = context.bot_data["lastfm_service"]
    group_service: GroupService = context.bot_data["group_service"]

    user, track = await lastfm_service.get_now_playing(cb.owner_id)
    if not track or not track.artist:
        await query.answer("Could not determine current artist from Now Playing.", show_alert=True)
        return

    artist_name = track.artist.name if hasattr(track.artist, "name") else str(track.artist)
    chat_id = update.effective_chat.id
    chat_name = update.effective_chat.title or update.effective_chat.username or "this chat"

    response_text, _ = await group_service.get_whoknows(chat_id, chat_name, artist_name)
    if update.effective_message:
        await update.effective_message.reply_text(response_text)


CALLBACK_ROUTES = {
    Action.NP_LESS: _handle_np_less,
    Action.NP_LESS_COVER: _handle_np_less_cover,
    Action.NP_MORE: _handle_np_more,
    Action.PREF_UNLINK: _handle_pref_unlink,
    Action.PREF_OPT_OUT: _handle_pref_opt_out,
    Action.TOPS: _handle_tops,
    Action.COLLAGE: _handle_collage,
    Action.WHOKNOWS: _handle_whoknows_button,
}


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route callback queries to appropriate handlers using typed Callback data."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    cb = Callback.decode(query.data or "")
    if not cb:
        logger.error(f"Invalid callback data: {query.data}")
        return

    handler = CALLBACK_ROUTES.get(cb.action)
    if not handler:
        logger.error(f"No handler for action: {cb.action} (data: {query.data})")
        return

    await handler(update, context, cb)


@log_command(START_COMMAND)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message to the user."""
    user = update.effective_user
    if user:
        logger.info(
            f"username: {user.username} - id: {user.id} started a chat with the bot"
        )
    view_service: ViewService = context.bot_data["view_service"]
    response = await view_service.build_start_response(user)
    if update.effective_message:
        await update.effective_message.reply_text(response)


@log_command(NOW_PLAYING_COMMAND)
async def now_playing(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    show_cover: bool = False,
    telegram_user_id: Optional[int] = None,
) -> None:
    """Fetches and displays the user's currently playing track."""
    from_button = update.callback_query is not None
    message = update.callback_query.message if from_button else update.effective_message
    user_id = telegram_user_id or (
        update.effective_user.id if update.effective_user else None
    )
    if not user_id or not message:
        return

    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup, cover_url = await view_service.build_np_response(
        user_id, show_cover
    )

    if from_button and show_cover:
        if cover_url:
            await message.edit_media(
                telegram.InputMediaPhoto(media=cover_url, caption=response),
                reply_markup=reply_markup,
            )
        else:
            # No cover available - just edit the text and remove the cover button
            await message.edit_text(response, reply_markup=reply_markup)
    else:
        await message.reply_text(response, reply_markup=reply_markup)


@log_command(SET_COMMAND)
async def lastfm_username_set(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Sets the user's Last.fm username."""
    user = update.effective_user
    message = update.effective_message
    if not message or not user:
        return

    logger.info(
        f"username: {user.username} - issued command: {message.text or SET_COMMAND}"
    )
    if not context.args:
        await message.reply_text(
            "Please provide a Last.fm username. Usage: /set <username>"
        )
        return

    lastfm_username = context.args[0]
    view_service: ViewService = context.bot_data["view_service"]
    response = await view_service.build_lastfm_username_set_response(
        telegram_user=user, lastfm_username=lastfm_username
    )
    await message.reply_text(response)


@log_command(STATUS_COMMAND)
async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    show_cover: bool = False,
    telegram_user_id: Optional[int] = None,
) -> None:
    """Fetches and displays the user's recent tracks."""
    from_button = update.callback_query is not None
    message = update.callback_query.message if from_button else update.effective_message
    user_id = telegram_user_id or (
        update.effective_user.id if update.effective_user else None
    )
    if not user_id or not message:
        return

    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup, cover_url = await view_service.build_status_response(
        user_id, show_cover
    )

    if from_button and show_cover:
        await message.edit_media(
            telegram.InputMediaPhoto(media=cover_url, caption=response),
            reply_markup=reply_markup,
        )
    else:
        await message.reply_text(response, reply_markup=reply_markup)


@log_command(TOPS_COMMAND)
async def tops(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_user_id: Optional[int] = None,
    entity_type: Optional[lastfm.EntityType] = None,
    period: Optional[lastfm.Period] = None,
) -> None:
    """Shows the user's top artists, albums or tracks."""
    from_button = update.callback_query is not None

    if from_button:
        query = update.callback_query
        if query and query.from_user:
            logger.info(
                f"username: {query.from_user.username} - pressed button: {query.data}"
            )
        message = update.callback_query.message if update.callback_query else None
        user_id = telegram_user_id
    else:
        user = update.effective_user
        message = update.effective_message
        if user:
            logger.info(
                f"username: {user.username} - issued command: {message.text if message else TOPS_COMMAND}"
            )
        user_id = user.id if user else None

        if context.args:
            entity_type, period = _parse_tops_args(context.args)

    if not user_id or not message:
        return

    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup = await view_service.build_tops_response(
        user_id, entity_type, period
    )

    if from_button:
        await message.edit_text(response, reply_markup=reply_markup)
    else:
        await message.reply_text(response, reply_markup=reply_markup)


def _parse_tops_args(
    args: list[str],
) -> tuple[Optional[lastfm.EntityType], Optional[lastfm.Period]]:
    """Parse command arguments for tops command."""
    entity_type = None
    period = None

    if args:
        entity_map = {
            "artists": lastfm.EntityType.ARTIST,
            "artist": lastfm.EntityType.ARTIST,
            "albums": lastfm.EntityType.ALBUM,
            "album": lastfm.EntityType.ALBUM,
            "tracks": lastfm.EntityType.TRACK,
            "track": lastfm.EntityType.TRACK,
        }
        entity_type = entity_map.get(args[0].lower())

    if len(args) > 1:
        period_map = {
            "1week": lastfm.Period.WEEK,
            "week": lastfm.Period.WEEK,
            "1month": lastfm.Period.ONE_MONTH,
            "month": lastfm.Period.ONE_MONTH,
            "3months": lastfm.Period.THREE_MONTHS,
            "3month": lastfm.Period.THREE_MONTHS,
            "6months": lastfm.Period.SIX_MONTHS,
            "6month": lastfm.Period.SIX_MONTHS,
            "12months": lastfm.Period.YEAR,
            "12month": lastfm.Period.YEAR,
            "year": lastfm.Period.YEAR,
            "overall": lastfm.Period.OVERALL,
            "alltime": lastfm.Period.OVERALL,
        }
        period = period_map.get(args[1].lower())

    return entity_type, period


@log_command(COLLAGE_COMMAND)
async def collage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates a Last.fm collage image."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    logger.info(
        f"username: {user.username} - issued command: {message.text or COLLAGE_COMMAND}"
    )
    user_id = user.id
    db_user = db.get_user(user_id)
    if not db_user:
        await message.reply_text(emojize(responses.user_not_found.substitute()))
        return

    view_service: ViewService = context.bot_data["view_service"]
    collage_service: CollageService = context.bot_data["collage_service"]

    if not context.args:
        # Show interactive selection
        response, reply_markup = await view_service.build_collage_selection_response(
            user_id
        )
        await message.reply_text(response, reply_markup=reply_markup)
        return

    # Parse arguments
    try:
        options = parse_collage_args(context.args)
    except ValueError as e:
        await message.reply_text(f"⚠️ {e}")
        return

    if options.preset:
        size_str = options.preset
    else:
        size_str = f"{options.cols}x{options.rows}"
    status_msg = await message.reply_text(
        f"🎨 Generating your {size_str} {options.entity} collage..."
    )
    if update.effective_chat:
        try:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=telegram.constants.ChatAction.UPLOAD_PHOTO,
            )
        except Exception:
            pass

    try:
        async with COLLAGE_SEMAPHORE:
            bio = await collage_service.generate_collage_image(
                username=db_user.lastfm_username, options=options
            )
        caption = view_service.build_collage_caption(
            entity_type=options.entity,
            size=size_str,
            period=options.period,
            lastfm_username=db_user.lastfm_username,
            tile_size=options.tile_size,
            theme=options.theme,
            overlay_style=options.overlay_style,
            preset=options.preset,
            show_text=options.show_text,
        )
        await message.reply_photo(photo=bio, caption=caption)
    except Exception as e:
        logger.exception(f"Error generating collage: {e}")
        await message.reply_text(
            emojize(responses.collage_error.substitute(error=str(e)))
        )
    finally:
        try:
            await status_msg.delete()
        except Exception:
            pass


@log_command(PREFERENCES_COMMAND)
async def preferences(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays user preferences options."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    logger.info(
        f"username: {user.username} - issued command: {message.text or PREFERENCES_COMMAND}"
    )
    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup = await view_service.build_preferences_response(user.id)
    await message.reply_text(response, reply_markup=reply_markup)


async def unlink_account(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_user_id: Optional[int] = None,
) -> None:
    """Unlinks a user's Last.fm account."""
    query = update.callback_query
    if not query:
        return

    user_id = telegram_user_id or query.from_user.id
    view_service: ViewService = context.bot_data["view_service"]
    response = view_service.build_preferences_unlink_account_response(user_id)
    await query.edit_message_text(text=response)


@log_command(HELP_COMMAND)
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the bot's description as help text."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    logger.info(
        f"username: {user.username} - issued command: {message.text or HELP_COMMAND}"
    )
    bot_description = (await context.bot.get_my_description()).description
    await message.reply_text(emojize(bot_description))


@log_command(CHANGELOG_COMMAND)
async def changelog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the changelog."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    logger.info(
        f"username: {user.username} - issued command: {message.text or CHANGELOG_COMMAND}"
    )
    view_service: ViewService = context.bot_data["view_service"]
    response = await view_service.build_changelog_response()
    await message.reply_text(response)


@log_command(PRIVACY_COMMAND)
async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the privacy policy."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    logger.info(
        f"username: {user.username} - issued command: {message.text or PRIVACY_COMMAND}"
    )
    view_service: ViewService = context.bot_data["view_service"]
    message_text = await view_service.build_privacy_response()
    await message.reply_text(message_text)


@log_command(COMPARE_COMMAND)
async def compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Compares listening stats between the user and another Last.fm user."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    logger.info(
        f"username: {user.username} - issued command: {message.text or COMPARE_COMMAND}"
    )
    if not context.args:
        await message.reply_text(
            "Please provide a Last.fm username. Usage: /compare <lastfm_username>"
        )
        return

    other_username = context.args[0]
    view_service: ViewService = context.bot_data["view_service"]
    response = await view_service.build_compare_response(user.id, other_username)
    await message.reply_text(response)


@log_command(VIBE_COMMAND)
async def vibe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates an AI description of the user's current listening vibe."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    logger.info(
        f"username: {user.username} - issued command: {message.text or VIBE_COMMAND}"
    )
    user_id = user.id
    lastfm_service = context.bot_data["view_service"].lastfm_service

    # Get recent tracks
    recent_tracks = await lastfm_service.get_recent_tracks(user_id)
    if not recent_tracks:
        await message.reply_text(
            "Couldn't find your recent tracks. Make sure your Last.fm is set up with /set"
        )
        return

    if update.effective_chat:
        try:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=telegram.constants.ChatAction.TYPING,
            )
        except Exception:
            pass

    status_msg = await message.reply_text("🎵 Analyzing your vibe...")

    # Format tracks for AI
    track_list = [
        f"{t.track.artist.name} - {t.track.title}" for t in recent_tracks[:10]
    ]
    current = track_list[0] if track_list else None

    # Generate vibe
    try:
        vibe_text = await ai.generate_vibe(track_list, current)
        escaped_vibe = html.escape(vibe_text)
        await message.reply_text(f"🎧 <b>Your Vibe</b>\n\n{escaped_vibe}")
    finally:
        try:
            await status_msg.delete()
        except Exception:
            pass


@log_command(ROAST_COMMAND)
async def roast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates a humorous AI roast of the user's music taste."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    logger.info(
        f"username: {user.username} - issued command: {message.text or ROAST_COMMAND}"
    )
    user_id = user.id
    lastfm_service = context.bot_data["view_service"].lastfm_service

    # Get top artists and tracks
    top_artists, top_tracks = await asyncio.gather(
        lastfm_service.get_tops(
            user_id, lastfm.EntityType.ARTIST, lastfm.Period.OVERALL
        ),
        lastfm_service.get_tops(
            user_id, lastfm.EntityType.TRACK, lastfm.Period.OVERALL
        ),
    )

    if not top_artists:
        await message.reply_text(
            "Couldn't find your top artists. Make sure your Last.fm is set up with /set"
        )
        return

    if update.effective_chat:
        try:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=telegram.constants.ChatAction.TYPING,
            )
        except Exception:
            pass

    status_msg = await message.reply_text("🔥 Preparing your roast...")

    # Format for AI
    artists_list = [item.item.name for item in top_artists[:10]]
    tracks_list = [
        f"{item.item.artist} - {item.item.title}" for item in (top_tracks or [])[:5]
    ]

    # Generate roast
    try:
        roast_text = await ai.generate_roast(artists_list, tracks_list)
        escaped_roast = html.escape(roast_text)
        await message.reply_text(f"🎤 <b>Music Taste Roast</b>\n\n{escaped_roast}")
    finally:
        try:
            await status_msg.delete()
        except Exception:
            pass


@log_command(RECOMMEND_COMMAND)
async def recommend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates AI-powered music recommendations."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    logger.info(
        f"username: {user.username} - issued command: {message.text or RECOMMEND_COMMAND}"
    )
    user_id = user.id
    lastfm_service = context.bot_data["view_service"].lastfm_service

    # Get top artists
    top_artists = await lastfm_service.get_tops(
        user_id, lastfm.EntityType.ARTIST, lastfm.Period.OVERALL
    )

    if not top_artists:
        await message.reply_text(
            "Couldn't find your top artists. Make sure your Last.fm is set up with /set"
        )
        return

    if update.effective_chat:
        try:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=telegram.constants.ChatAction.TYPING,
            )
        except Exception:
            pass

    status_msg = await message.reply_text("🎵 Finding recommendations for you...")

    # Format for AI
    artists_list = [item.item.name for item in top_artists[:10]]

    # Generate recommendations
    try:
        rec_text = await ai.generate_recommendations(artists_list)
        escaped_rec = html.escape(rec_text)
        await message.reply_text(
            f"💡 <b>Recommendations Based On Your Taste</b>\n\n{escaped_rec}"
        )
    finally:
        try:
            await status_msg.delete()
        except Exception:
            pass


@log_command(WHOKNOWS_COMMAND)
async def whoknows(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows who in the current chat listens to a specific artist."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return

    group_service: GroupService = context.bot_data["group_service"]
    lastfm_service: LastfmService = context.bot_data["lastfm_service"]
    chat_id = chat.id
    chat_name = chat.title or chat.username or "this chat"

    artist_query = ""
    if context.args:
        artist_query = " ".join(context.args).strip()
    elif message.reply_to_message and message.reply_to_message.text:
        reply_text = message.reply_to_message.text.strip()
        if "🎧" in reply_text and "—" in reply_text:
            try:
                part = reply_text.split("🎧")[1].split("—")[0].strip()
                artist_query = part
            except Exception:
                artist_query = reply_text
        else:
            artist_query = reply_text
    else:
        # Fallback to caller's Now Playing track
        _, track = await lastfm_service.get_now_playing(user.id)
        if track and track.artist:
            artist_query = (
                track.artist.name
                if hasattr(track.artist, "name")
                else str(track.artist)
            )

    if not artist_query:
        await message.reply_text(
            emojize(responses.whoknows_specify_artist.substitute())
        )
        return

    try:
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=telegram.constants.ChatAction.TYPING,
        )
    except Exception:
        pass

    response_text, _ = await group_service.get_whoknows(
        chat_id, chat_name, artist_query
    )
    await message.reply_text(response_text)


@log_command(CROWNS_COMMAND)
async def crowns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows group crowns hall of fame or crowns held by a specific user."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return

    group_service: GroupService = context.bot_data["group_service"]
    chat_id = chat.id
    chat_name = chat.title or chat.username or "this chat"

    # Check if command is /mycrowns
    is_mycrowns = bool(
        message.text and message.text.startswith(f"/{MYCROWNS_ALIAS}")
    )

    if is_mycrowns:
        caller_user = db.get_user(user.id)
        if not caller_user:
            await message.reply_text(emojize(responses.user_not_found.substitute()))
            return
        response_text = await group_service.get_user_crowns_showcase(
            chat_id, chat_name, caller_user
        )
        await message.reply_text(response_text)
        return

    if context.args:
        target_arg = context.args[0].strip()
        target_user = db.get_user_by_username(target_arg)
        if not target_user and target_arg.isdigit():
            target_user = db.get_user(int(target_arg))

        if not target_user:
            await message.reply_text(
                f"🔎 No user found for: {html.escape(target_arg)}. Make sure they have interacted with the bot."
            )
            return

        response_text = await group_service.get_user_crowns_showcase(
            chat_id, chat_name, target_user
        )
        await message.reply_text(response_text)
        return

    # No arguments -> Show group Hall of Fame
    response_text = await group_service.get_crowns_hall_of_fame(chat_id, chat_name)
    await message.reply_text(response_text)

