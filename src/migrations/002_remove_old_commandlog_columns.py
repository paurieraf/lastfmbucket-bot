"""
Remove old chat_type column from CommandLog (now on Chat table).

Note: SQLite doesn't support DROP COLUMN before version 3.35.0.
This migration checks if the column exists and skips if not needed.
"""


def migrate(migrator, database, fake=False, **kwargs):
    """Remove old columns if they exist."""
    # Check current columns
    cursor = database.execute_sql("PRAGMA table_info(commandlog)")
    columns = [row[1] for row in cursor.fetchall()]

    # SQLite 3.35+ supports ALTER TABLE DROP COLUMN
    if "chat_type" in columns:
        try:
            database.execute_sql('ALTER TABLE "commandlog" DROP COLUMN "chat_type"')
        except Exception:
            # Older SQLite - skip, column will just be unused
            pass


def rollback(migrator, database, fake=False, **kwargs):
    """Rollback - re-add columns."""
    pass
