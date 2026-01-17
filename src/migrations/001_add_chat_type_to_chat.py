"""
Add chat_type column to Chat table and chat FK to CommandLog.
"""

import peewee as pw


def migrate(migrator, database, fake=False, **kwargs):
    """Add chat_type to Chat and chat FK to CommandLog."""
    # Use raw SQL for SQLite compatibility
    database.execute_sql('ALTER TABLE "chat" ADD COLUMN "chat_type" VARCHAR(255) DEFAULT ""')
    database.execute_sql('ALTER TABLE "commandlog" ADD COLUMN "chat_id" INTEGER REFERENCES "chat" ("id")')


def rollback(migrator, database, fake=False, **kwargs):
    """Rollback the migration."""
    # SQLite doesn't support DROP COLUMN easily, would need to recreate table
    pass
