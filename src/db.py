import logging

from peewee import BigIntegerField, CharField, ForeignKeyField, Model
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
    },
)

"""
Models
"""


class User(Model):
    telegram_id = BigIntegerField(unique=True)
    telegram_username = CharField(default="")
    lastfm_username = CharField(default="")

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


MODELS = [User, Chat, CommandLog]

"""
DB Connection
"""
db.connect()
# db.drop_tables(MODELS)
db.create_tables(MODELS)

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
            user.telegram_username = (telegram_username,)
            user.lastfm_username = lastfm_username
            user.save()
            logging.info(f"User updated: {user}")
        else:
            logging.info(f"User created: {user}")
    return user


def get_user(telegram_user_id: int) -> User | None:
    """
    Retrieves a user from the database based on their Telegram user ID.

    This function looks up and returns a user object using the
    provided Telegram ID. If the user does not exist,
    appropriate handling or behavior should be implemented
    in the calling code.

    :param telegram_user_id: The ID corresponding to a specific
        Telegram user.
    :type telegram_user_id: int
    :return: The user object associated with the given Telegram ID.
    :rtype: User
    """
    return User.get_or_none(telegram_id=telegram_user_id)


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


def log_command(
    user_id: int,
    username: str,
    command: str,
    args: str,
    chat_id: int,
    chat_type: str,
    chat_name: str = "",
) -> CommandLog:
    """Logs a command execution to the database."""
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
        if not created and (chat.telegram_chat_name != chat_name or chat.chat_type != chat_type):
            chat.telegram_chat_name = chat_name
            chat.chat_type = chat_type
            chat.save()
    return chat


def create_or_update_chat(telegram_chat_id: int, telegram_chat_name: str) -> Chat:
    """
    Creates or updates a chat entry in the database. If a chat with the given
    telegram_chat_id exists, its name will be updated to the provided
    telegram_chat_name. Otherwise, a new chat record is created using the given
    details. Log messages are recorded for both creation and update events.

    :param telegram_chat_id: Unique identifier for the chat in Telegram.
    :type telegram_chat_id: int
    :param telegram_chat_name: Name of the Telegram chat.
    :type telegram_chat_name: str
    :return: The corresponding Chat object after creation or update.
    :rtype: Chat
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
