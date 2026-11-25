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
        "synchronous": 1,  # NORMAL durability (safe with WAL mode).
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
    user_id = BigIntegerField(index=True)
    username = CharField(default="")
    command = CharField(index=True)
    args = CharField(default="")
    chat = ForeignKeyField(Chat, backref="command_logs", null=True)
    timestamp = BigIntegerField(index=True)  # Unix timestamp

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
DB Connection & Migrations
"""


def run_migrations(database=None) -> None:
    """
    Ensure schema migrations are applied to existing database tables.
    Peewee's create_tables(safe=True) only creates missing tables; it does
    not alter or add missing columns to already existing SQLite tables.
    """
    target_db = database or db

    # Table columns to ensure exist: (table_name, column_name, sql_definition)
    expected_columns = [
        ("user", "group_opt_out", "INTEGER NOT NULL DEFAULT 0"),
        ("chat", "telegram_chat_name", "TEXT NOT NULL DEFAULT ''"),
        ("chat", "chat_type", "TEXT NOT NULL DEFAULT ''"),
        ("commandlog", "args", "TEXT NOT NULL DEFAULT ''"),
        ("commandlog", "chat_id", "INTEGER NULL"),
        ("chatmember", "opt_out", "INTEGER NOT NULL DEFAULT 0"),
    ]

    for table_name, column_name, col_def in expected_columns:
        try:
            cursor = target_db.execute_sql(f"PRAGMA table_info('{table_name}')")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if existing_cols and column_name not in existing_cols:
                logger.info(
                    f"Applying DB migration: adding '{column_name}' column to '{table_name}' table"
                )
                target_db.execute_sql(
                    f"ALTER TABLE '{table_name}' ADD COLUMN {column_name} {col_def}"
                )
        except Exception as e:
            logger.error(
                f"Failed to migrate '{column_name}' on '{table_name}': {e}",
                exc_info=True,
            )

    expected_indexes = [
        ("commandlog", "idx_commandlog_timestamp", "timestamp"),
        ("commandlog", "idx_commandlog_user_id", "user_id"),
        ("commandlog", "idx_commandlog_command", "command"),
    ]
    for table_name, index_name, column_name in expected_indexes:
        try:
            cursor = target_db.execute_sql(f"PRAGMA table_info('{table_name}')")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if existing_cols and column_name in existing_cols:
                target_db.execute_sql(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
                )
        except Exception as e:
            logger.error(
                f"Failed to create index '{index_name}' on '{table_name}': {e}",
                exc_info=True,
            )


db.connect()
db.create_tables(MODELS, safe=True)
run_migrations()

"""
DB Methods
"""


def create_or_update_user(
    telegram_user_id: int, telegram_username: str | None, lastfm_username: str | None
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
    clean_tg_username = telegram_username or ""
    clean_lfm_username = (lastfm_username or "").strip()
    with db.atomic():
        user, created = User.get_or_create(
            telegram_id=telegram_user_id,
            defaults={
                "telegram_username": clean_tg_username,
                "lastfm_username": clean_lfm_username,
            },
        )

        if not created:
            user.telegram_username = clean_tg_username
            user.lastfm_username = clean_lfm_username
            user.save()
            logger.info(f"User updated: {user}")
        else:
            logger.info(f"User created: {user}")
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


def get_linked_user(telegram_user_id: int) -> User | None:
    """
    Retrieves a user from the database only if they have linked a non-empty
    Last.fm username (ignoring placeholder rows created by chat tracking).
    """
    user = get_user(telegram_user_id)
    if not user or not (user.lastfm_username or "").strip():
        return None
    return user


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
    Deletes a user and all associated data (memberships, crowns, command logs)
    from the database based on their Telegram user ID.

    :param telegram_user_id: The ID corresponding to a specific
        Telegram user.
    :type telegram_user_id: int
    """
    with db.atomic():
        user = User.get_or_none(telegram_id=telegram_user_id)
        if user:
            user.delete_instance(recursive=True)
            logger.info(f"User with telegram_id {telegram_user_id} deleted.")
        deleted_logs = (
            CommandLog.delete()
            .where(CommandLog.user_id == telegram_user_id)
            .execute()
        )
        if deleted_logs:
            logger.info(
                f"Deleted {deleted_logs} command log(s) for telegram_id {telegram_user_id}."
            )


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
    chat_id: int, artist_name: str, artist_url: str, user: User, playcount: int
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
    Returns list of dicts with user, crown_count, and samples.
    """
    chat = Chat.get_or_none(telegram_id=chat_id)
    if not chat:
        return []

    # Query 2: Eagerly join User and count crowns per user
    crown_counts = list(
        Crown.select(Crown.user, User, fn.COUNT(Crown.id).alias("count"))
        .join(User)
        .where(Crown.chat == chat)
        .group_by(Crown.user)
        .order_by(SQL("count DESC"))
        .limit(limit)
    )
    if not crown_counts:
        return []

    # Query 3: Single batched window-function query for top-3 sample crowns per user
    user_ids = [entry.user_id for entry in crown_counts]
    placeholders = ", ".join("?" for _ in user_ids)
    cursor = db.execute_sql(
        f"""
        SELECT user_id, artist_name, artist_url, playcount
        FROM (
            SELECT
                user_id,
                artist_name,
                artist_url,
                playcount,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id
                    ORDER BY playcount DESC, id ASC
                ) AS rn
            FROM crown
            WHERE chat_id = ? AND user_id IN ({placeholders})
        ) ranked
        WHERE rn <= 3
        ORDER BY user_id, rn ASC
        """,
        [chat.id, *user_ids],
    )

    samples_by_user: dict[int, list[dict]] = {}
    for user_id, artist_name, artist_url, playcount in cursor.fetchall():
        samples_by_user.setdefault(user_id, []).append(
            {"name": artist_name, "url": artist_url, "plays": playcount}
        )

    return [
        {
            "user": entry.user,
            "crown_count": entry.count,
            "samples": samples_by_user.get(entry.user_id, []),
        }
        for entry in crown_counts
    ]


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
    """Gets or creates a chat entry in the database without overwriting non-empty metadata with empty values."""
    with db.atomic():
        chat, created = Chat.get_or_create(
            telegram_id=telegram_chat_id,
            defaults={"telegram_chat_name": chat_name, "chat_type": chat_type},
        )
        if not created:
            updated = False
            if chat_name and chat.telegram_chat_name != chat_name:
                chat.telegram_chat_name = chat_name
                updated = True
            if chat_type and chat.chat_type != chat_type:
                chat.chat_type = chat_type
                updated = True
            if updated:
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
            logger.info(f"Chat updated: {chat}")
        else:
            logger.info(f"Chat created: {chat}")
    return chat
