"""
Add chat_type column to Chat table and update CommandLog FK.

Peewee migrations, see http://docs.peewee-orm.com/en/latest/peewee/playhouse.html#schema-migrations
"""

from peewee import CharField, ForeignKeyField, BigIntegerField


def migrate(migrator, database, fake=False, **kwargs):
    """Add chat_type to Chat and chat FK to CommandLog."""
    # Add chat_type to Chat table
    migrator.add_column("chat", "chat_type", CharField(default=""))

    # Add chat_id FK column to CommandLog (Peewee stores FK as <field>_id)
    migrator.add_column("commandlog", "chat_id", BigIntegerField(null=True))


def rollback(migrator, database, fake=False, **kwargs):
    """Rollback the migration."""
    migrator.drop_column("chat", "chat_type")
    migrator.drop_column("commandlog", "chat_id")
