"""
Telegram bot command handlers.

This module contains handlers for commands and callback queries.
"""

import logging
from typing import Optional

import telegram.constants
from dotenv import load_dotenv
from emoji import emojize
from telegram import LinkPreviewOptions, Update
from telegram.ext import ContextTypes

import lastfm
from callbacks import Action, Callback
from services import ViewService

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# Command constants
START_COMMAND = "start"
STATUS_COMMAND = "status"
NOW_PLAYING_COMMAND = "np"
TOPS_COMMAND = "tops"
PREFERENCES_COMMAND = "preferences"
HELP_COMMAND = "help"
CHANGELOG_COMMAND = "changelog"
SET_COMMAND = "set"
PRIVACY_COMMAND = "privacy"


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


CALLBACK_ROUTES = {
    Action.NP_LESS: _handle_np_less,
    Action.NP_LESS_COVER: _handle_np_less_cover,
    Action.NP_MORE: _handle_np_more,
    Action.PREF_UNLINK: _handle_pref_unlink,
    Action.TOPS: _handle_tops,
}


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route callback queries to appropriate handlers using typed Callback data."""
    query = update.callback_query
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message to the user."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- id: {update.message.from_user.id} started a private chat with the bot"
    )
    view_service: ViewService = context.bot_data["view_service"]
    response = await view_service.build_start_response(update.message.from_user)
    await update.message.reply_text(response)


async def now_playing(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    show_cover: bool = False,
    telegram_user_id: Optional[int] = None,
) -> None:
    """Fetches and displays the user's currently playing track."""
    from_button = update.callback_query is not None
    message = update.callback_query.message if from_button else update.message
    user_id = telegram_user_id or update.message.from_user.id

    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup, cover_url = await view_service.build_np_response(
        user_id, show_cover
    )

    if from_button and show_cover and cover_url:
        await message.edit_media(
            telegram.InputMediaPhoto(
                media=cover_url,
                caption=response,
                parse_mode=telegram.constants.ParseMode.HTML,
            ),
            reply_markup=reply_markup,
        )
    else:
        await message.reply_html(
            response,
            reply_markup=reply_markup,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )


async def lastfm_username_set(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Sets the user's Last.fm username."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- issued command: {update.message.text}"
    )
    if not context.args:
        await update.message.reply_text("Please provide a Last.fm username.")
        return

    lastfm_username = context.args[0]
    view_service: ViewService = context.bot_data["view_service"]
    response = await view_service.build_lastfm_username_set_response(
        telegram_user=update.message.from_user, lastfm_username=lastfm_username
    )
    await update.message.reply_text(response)


async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    show_cover: bool = False,
    telegram_user_id: Optional[int] = None,
) -> None:
    """Fetches and displays the user's recent tracks."""
    from_button = update.callback_query is not None
    message = update.callback_query.message if from_button else update.message
    user_id = telegram_user_id or update.message.from_user.id

    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup, cover_url = await view_service.build_status_response(
        user_id, show_cover
    )

    if from_button and show_cover:
        await message.edit_media(
            telegram.InputMediaPhoto(
                media=cover_url,
                caption=response,
                parse_mode=telegram.constants.ParseMode.HTML,
            ),
            reply_markup=reply_markup,
        )
    else:
        await message.reply_html(
            response,
            reply_markup=reply_markup,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )


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
        logger.info(
            f"username: {update.callback_query.from_user.username} "
            f"- pressed button: {update.callback_query.data}"
        )
        message = update.callback_query.message
        user_id = telegram_user_id
    else:
        logger.info(
            f"username: {update.message.from_user.username} "
            f"- issued command: {update.message.text}"
        )
        message = update.message
        user_id = update.message.from_user.id

        if context.args:
            entity_type, period = _parse_tops_args(context.args)

    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup = await view_service.build_tops_response(
        user_id, entity_type, period
    )

    if from_button:
        await message.edit_text(
            response,
            reply_markup=reply_markup,
            parse_mode=telegram.constants.ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    else:
        await message.reply_html(
            response,
            reply_markup=reply_markup,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )


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


async def preferences(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays user preferences options."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- issued command: {update.message.text}"
    )
    view_service: ViewService = context.bot_data["view_service"]
    response, reply_markup = await view_service.build_preferences_response(
        update.message.from_user.id
    )
    await update.message.reply_html(response, reply_markup=reply_markup)


async def unlink_account(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_user_id: Optional[int] = None,
) -> None:
    """Unlinks a user's Last.fm account."""
    query = update.callback_query
    user_id = telegram_user_id or query.from_user.id
    view_service: ViewService = context.bot_data["view_service"]
    response = view_service.build_preferences_unlink_account_response(user_id)
    await query.edit_message_text(text=response)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the bot's description as help text."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- issued command: {update.message.text}"
    )
    bot_description = (await context.bot.get_my_description()).description
    await update.message.reply_text(emojize(bot_description))


async def changelog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """TODO: Implement changelog command."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- issued command: {update.message.text}"
    )
    await update.message.reply_text("Hello!")


async def privacy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the privacy policy."""
    logger.info(
        f"username: {update.message.from_user.username} "
        f"- issued command: {update.message.text}"
    )
    view_service: ViewService = context.bot_data["view_service"]
    message = await view_service.build_privacy_response()
    await update.message.reply_html(message)
