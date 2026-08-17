import logging

from peewee import (
    BigIntegerField,
    BooleanField,
    CharField,
    ForeignKeyField,
    Model,
    SQL,
    fn,
)
from playhouse.sqlite_ext import SqliteExtDatabase

import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

"""
Globals variables
"""

db = SqliteExtDatabase(
    config.DB_SQLITE_NAME,
    pragmas={
        "journal_mode": "wal",  # WAL-mode.
        "cache_size": -1 * 64000,  # 64MB cache.
        "foreign_keys": 1,  # Enforce foreign-key constraints
        "ignore_check_constraints": 0,  # Enforce CHECK constraints
        "synchronous": 0,  # Let the OS manage syncing.
        "busy_timeout": 5000,  # Wait up to 5s on lock contention (admin process shares DB).
    },
)

"""
Models
"""


class User(Model):
    telegram_id = BigIntegerField(unique=True)
    telegram_username = CharField(default="")
    lastfm_username = CharField(default="")
    group_opt_out = BooleanField(default=False)

    class Meta:
        database = db


class Chat(Model):
    telegram_id = BigIntegerField(unique=True)
    telegram_chat_name = CharField(default="")
    chat_type = CharField(default="")  # private, group, supergroup, channel

    class Meta:
        database = db


class CommandLog(Model):
    user_id = BigIntegerField()
    username = CharField(default="")
    command = CharField()
    args = CharField(default="")
    chat = ForeignKeyField(Chat, backref="command_logs", null=True)
    timestamp = BigIntegerField()  # Unix timestamp

    class Meta:
        database = db


class ChatMember(Model):
    chat = ForeignKeyField(Chat, backref="members", on_delete="CASCADE")
    user = ForeignKeyField(User, backref="chat_memberships", on_delete="CASCADE")
    last_active = BigIntegerField()  # Unix timestamp
    opt_out = BooleanField(default=False)

    class Meta:
        database = db
        indexes = ((("chat", "user"), True),)


class Crown(Model):
    chat = ForeignKeyField(Chat, backref="crowns", on_delete="CASCADE")
    artist_name = CharField(index=True)
    artist_url = CharField(default="")
    user = ForeignKeyField(User, backref="crowns", on_delete="CASCADE")
    playcount = BigIntegerField(default=0)
    updated_at = BigIntegerField()  # Unix timestamp

    class Meta:
        database = db
        indexes = ((("chat", "artist_name"), True),)


MODELS = [User, Chat, CommandLog, ChatMember, Crown]

"""
DB Connection
"""
db.connect()
db.create_tables(MODELS, safe=True)

"""
DB Methods
"""


def create_or_update_user(
    telegram_user_id: int, telegram_username: str, lastfm_username: str | None
) -> User:
    """
    Creates or updates a user in the database based on the given parameters. If the
    user identified by the provided telegram_user_id does not already exist, a new
    user is created with the given default values. Otherwise, the existing user's
    information is updated with the provided telegram_username and lastfm_username.

    :param telegram_user_id: The unique identifier for the user in Telegram.
    :param telegram_username: The username of the user in Telegram.
    :param lastfm_username: The username of the user in Last.fm. This parameter
        can be None.
    :return: The User object that was created or updated.
    """
    with db.atomic():
        user, created = User.get_or_create(
            telegram_id=telegram_user_id,
            defaults={
                "telegram_username": telegram_username,
                "lastfm_username": lastfm_username,
            },
        )

        if not created:
            user.telegram_username = telegram_username
            user.lastfm_username = lastfm_username
            user.save()
            logging.info(f"User updated: {user}")
        else:
            logging.info(f"User created: {user}")
    return user


def get_user(telegram_user_id: int) -> User | None:
    """
    Retrieves a user from the database based on their Telegram user ID.

    :param telegram_user_id: The ID corresponding to a specific
        Telegram user.
    :type telegram_user_id: int
    :return: The user object associated with the given Telegram ID.
    :rtype: User
    """
    return User.get_or_none(telegram_id=telegram_user_id)


def get_user_by_username(username: str) -> User | None:
    """
    Retrieves a user from the database based on their Telegram @username.

    :param username: Telegram username (with or without '@').
    :return: The user object if found.
    """
    clean_username = username.lstrip("@").strip()
    if not clean_username:
        return None
    return User.get_or_none(fn.Lower(User.telegram_username) == clean_username.lower())


def delete_user(telegram_user_id: int) -> None:
    """
    Deletes a user from the database based on their Telegram user ID.

    :param telegram_user_id: The ID corresponding to a specific
        Telegram user.
    :type telegram_user_id: int
    """
    with db.atomic():
        user = User.get_or_none(telegram_id=telegram_user_id)
        if user:
            user.delete_instance()
            logging.info(f"User with telegram_id {telegram_user_id} deleted.")


def toggle_user_group_opt_out(telegram_user_id: int) -> bool:
    """
    Toggles the group ranking opt_out setting for a user.
    Returns the new opt_out status (True if opted out, False if visible).
    """
    with db.atomic():
        user = User.get_or_none(telegram_id=telegram_user_id)
        if not user:
            return False
        user.group_opt_out = not user.group_opt_out
        user.save()
        # Also update all existing ChatMember rows for this user
        ChatMember.update(opt_out=user.group_opt_out).where(
            ChatMember.user == user
        ).execute()
        return user.group_opt_out


def track_chat_member(
    chat_id: int,
    user_id: int,
    username: str = "",
    chat_name: str = "",
    chat_type: str = "",
) -> ChatMember | None:
    """
    Tracks a user's membership and activity in a chat.
    Auto-discovers and registers members transparently.
    """
    import time

    if chat_id == 0 or user_id == 0:
        return None

    with db.atomic():
        chat = get_or_create_chat(chat_id, chat_name, chat_type)
        user = User.get_or_none(telegram_id=user_id)
        if not user:
            # Create minimal user placeholder if not exists
            user, _ = User.get_or_create(
                telegram_id=user_id,
                defaults={"telegram_username": username, "lastfm_username": ""},
            )
        elif username and user.telegram_username != username:
            user.telegram_username = username
            user.save()

        now = int(time.time())
        member, created = ChatMember.get_or_create(
            chat=chat,
            user=user,
            defaults={"last_active": now, "opt_out": user.group_opt_out},
        )
        if not created:
            member.last_active = now
            member.opt_out = user.group_opt_out
            member.save()

    return member


def get_linked_chat_members(chat_id: int) -> list[User]:
    """
    Retrieves all active, non-opt-out users in a chat who have linked Last.fm accounts.
    """
    chat = Chat.get_or_none(telegram_id=chat_id)
    if not chat:
        return []

    query = (
        User.select()
        .join(ChatMember, on=(ChatMember.user == User.id))
        .where(
            (ChatMember.chat == chat)
            & (~ChatMember.opt_out)
            & (~User.group_opt_out)
            & (User.lastfm_username != "")
            & (User.lastfm_username.is_null(False))
        )
    )
    return list(query)


def get_crown(chat_id: int, artist_name: str) -> Crown | None:
    """
    Retrieves the current crown holder for an artist in a chat.
    """
    chat = Chat.get_or_none(telegram_id=chat_id)
    if not chat:
        return None
    return (
        Crown.select()
        .where(
            (Crown.chat == chat)
            & (fn.Lower(Crown.artist_name) == artist_name.strip().lower())
        )
        .first()
    )


def upsert_crown(
    chat_id: int,
    artist_name: str,
    artist_url: str,
    user: User,
    playcount: int,
) -> tuple[Crown, Crown | None]:
    """
    Updates or inserts a crown for an artist in a chat.
    Returns a tuple of (current_crown, previous_crown_or_none).
    """
    import time

    now = int(time.time())
    with db.atomic():
        chat = get_or_create_chat(chat_id)
        existing_crown = (
            Crown.select()
            .where(
                (Crown.chat == chat)
                & (fn.Lower(Crown.artist_name) == artist_name.strip().lower())
            )
            .first()
        )

        previous_crown = None
        if existing_crown:
            # Clone previous state for comparison
            previous_crown = Crown(
                chat=existing_crown.chat,
                artist_name=existing_crown.artist_name,
                artist_url=existing_crown.artist_url,
                user=existing_crown.user,
                playcount=existing_crown.playcount,
                updated_at=existing_crown.updated_at,
            )
            existing_crown.artist_name = artist_name  # Canonical casing
            if artist_url:
                existing_crown.artist_url = artist_url
            existing_crown.user = user
            existing_crown.playcount = playcount
            existing_crown.updated_at = now
            existing_crown.save()
            return existing_crown, previous_crown
        else:
            new_crown = Crown.create(
                chat=chat,
                artist_name=artist_name,
                artist_url=artist_url,
                user=user,
                playcount=playcount,
                updated_at=now,
            )
            return new_crown, None


def get_chat_crowns_leaderboard(chat_id: int, limit: int = 10) -> list[dict]:
    """
    Retrieves the crowns leaderboard for a chat (users with the most crowns).
    Returns list of dicts with user, crown_count, and sample_artists.
    """
    chat = Chat.get_or_none(telegram_id=chat_id)
    if not chat:
        return []

    # Count crowns per user
    crown_counts = (
        Crown.select(Crown.user, fn.COUNT(Crown.id).alias("count"))
        .where(Crown.chat == chat)
        .group_by(Crown.user)
        .order_by(SQL("count DESC"))
        .limit(limit)
    )

    leaderboard = []
    for entry in crown_counts:
        # Get top 3 sample crowned artists for this user
        sample_crowns = (
            Crown.select(Crown.artist_name, Crown.artist_url, Crown.playcount)
            .where((Crown.chat == chat) & (Crown.user == entry.user))
            .order_by(Crown.playcount.desc())
            .limit(3)
        )
        samples = [
            {"name": c.artist_name, "url": c.artist_url, "plays": c.playcount}
            for c in sample_crowns
        ]
        leaderboard.append(
            {
                "user": entry.user,
                "crown_count": entry.count,
                "samples": samples,
            }
        )

    return leaderboard


def get_user_crowns(chat_id: int, user_id: int) -> list[Crown]:
    """
    Retrieves all crowns held by a specific user in a chat.
    """
    chat = Chat.get_or_none(telegram_id=chat_id)
    user = User.get_or_none(telegram_id=user_id)
    if not chat or not user:
        return []

    return list(
        Crown.select()
        .where((Crown.chat == chat) & (Crown.user == user))
        .order_by(Crown.playcount.desc())
    )


def log_command(
    user_id: int,
    username: str,
    command: str,
    args: str,
    chat_id: int,
    chat_type: str,
    chat_name: str = "",
) -> CommandLog:
    """Logs a command execution to the database and tracks chat membership."""
    import time

    with db.atomic():
        chat = get_or_create_chat(chat_id, chat_name, chat_type)
        log_entry = CommandLog.create(
            user_id=user_id,
            username=username,
            command=command,
            args=args,
            chat=chat,
            timestamp=int(time.time()),
        )
    # Track chat membership
    track_chat_member(chat_id, user_id, username, chat_name, chat_type)
    return log_entry


def get_or_create_chat(
    telegram_chat_id: int, chat_name: str = "", chat_type: str = ""
) -> Chat:
    """Gets or creates a chat entry in the database."""
    with db.atomic():
        chat, created = Chat.get_or_create(
            telegram_id=telegram_chat_id,
            defaults={"telegram_chat_name": chat_name, "chat_type": chat_type},
        )
        if not created and (
            chat.telegram_chat_name != chat_name or chat.chat_type != chat_type
        ):
            chat.telegram_chat_name = chat_name
            chat.chat_type = chat_type
            chat.save()
    return chat


def create_or_update_chat(telegram_chat_id: int, telegram_chat_name: str) -> Chat:
    """
    Creates or updates a chat entry in the database.
    """
    with db.atomic():
        chat, created = Chat.get_or_create(
            telegram_id=telegram_chat_id,
            defaults={"telegram_chat_name": telegram_chat_name},
        )
        if not created:
            chat.telegram_chat_name = telegram_chat_name
            chat.save()
            logging.info(f"Chat updated: {chat}")
        else:
            logging.info(f"Chat created: {chat}")
    return chat
