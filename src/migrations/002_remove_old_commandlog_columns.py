"""
Remove old chat_id and chat_type columns from CommandLog.

This migration handles the case where CommandLog had direct chat_id and chat_type
fields instead of a FK to Chat.
"""


def migrate(migrator, database, fake=False, **kwargs):
    """Remove old columns if they exist."""
    # Check current columns
    cursor = database.execute_sql("PRAGMA table_info(commandlog)")
    columns = [row[1] for row in cursor.fetchall()]

    # Remove old chat_type from CommandLog (now on Chat table)
    if "chat_type" in columns:
        migrator.drop_column("commandlog", "chat_type")


def rollback(migrator, database, fake=False, **kwargs):
    """Rollback - re-add columns."""
    from peewee import CharField

    migrator.add_column("commandlog", "chat_type", CharField(default=""))
