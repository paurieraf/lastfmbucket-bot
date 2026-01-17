"""
Admin dashboard for LastfmBucket Bot using NiceGUI.

Provides a modern web interface to view and manage database models.
"""

import datetime
import os
import secrets

from nicegui import app, ui

from db import Chat, CommandLog, User

# Configuration from environment
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "5000"))
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", secrets.token_hex(16))

# Store for authenticated sessions
app.storage.secret = ADMIN_SECRET_KEY


def check_auth() -> bool:
    """Check if user is authenticated."""
    return app.storage.user.get("authenticated", False)


def format_timestamp(ts: int) -> str:
    """Format Unix timestamp to readable string."""
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


@ui.page("/login")
def login_page():
    """Login page."""

    def try_login():
        if username.value == ADMIN_USERNAME and password.value == ADMIN_PASSWORD:
            app.storage.user["authenticated"] = True
            ui.navigate.to("/")
        else:
            ui.notify("Invalid credentials", type="negative")

    with ui.card().classes("absolute-center"):
        ui.label("LastfmBucket Admin").classes("text-2xl font-bold mb-4")
        username = ui.input("Username").classes("w-full")
        password = ui.input("Password", password=True).classes("w-full")
        password.on("keydown.enter", try_login)
        ui.button("Login", on_click=try_login).classes("w-full mt-4")


@ui.page("/")
def dashboard():
    """Main dashboard page."""
    if not check_auth():
        return ui.navigate.to("/login")

    with ui.header().classes("bg-blue-600"):
        ui.label("LastfmBucket Admin").classes("text-xl text-white font-bold")
        ui.space()
        with ui.row():
            ui.button("Dashboard", on_click=lambda: ui.navigate.to("/")).props("flat color=white")
            ui.button("Users", on_click=lambda: ui.navigate.to("/users")).props("flat color=white")
            ui.button("Chats", on_click=lambda: ui.navigate.to("/chats")).props("flat color=white")
            ui.button("Command Logs", on_click=lambda: ui.navigate.to("/logs")).props(
                "flat color=white"
            )
            ui.button(
                "Logout",
                on_click=lambda: (
                    app.storage.user.clear(),
                    ui.navigate.to("/login"),
                ),
            ).props("flat color=white")

    with ui.column().classes("w-full p-4"):
        ui.label("Dashboard").classes("text-2xl font-bold mb-4")

        # Stats cards
        with ui.row().classes("w-full gap-4"):
            with ui.card().classes("bg-blue-500 text-white"):
                ui.label("Total Users").classes("text-sm opacity-80")
                ui.label(str(User.select().count())).classes("text-3xl font-bold")

            with ui.card().classes("bg-green-500 text-white"):
                ui.label("Total Chats").classes("text-sm opacity-80")
                ui.label(str(Chat.select().count())).classes("text-3xl font-bold")

            with ui.card().classes("bg-purple-500 text-white"):
                ui.label("Total Commands").classes("text-sm opacity-80")
                ui.label(str(CommandLog.select().count())).classes("text-3xl font-bold")

            today_start = int(
                datetime.datetime.now().replace(hour=0, minute=0, second=0).timestamp()
            )
            commands_today = (
                CommandLog.select().where(CommandLog.timestamp >= today_start).count()
            )
            with ui.card().classes("bg-orange-500 text-white"):
                ui.label("Commands Today").classes("text-sm opacity-80")
                ui.label(str(commands_today)).classes("text-3xl font-bold")

        # Recent commands
        ui.label("Recent Commands").classes("text-xl font-bold mt-6 mb-2")
        recent_commands = (
            CommandLog.select().order_by(CommandLog.timestamp.desc()).limit(10)
        )
        columns = [
            {"name": "time", "label": "Time", "field": "time", "align": "left"},
            {"name": "command", "label": "Command", "field": "command", "align": "left"},
            {"name": "username", "label": "User", "field": "username", "align": "left"},
            {"name": "args", "label": "Args", "field": "args", "align": "left"},
            {"name": "chat_type", "label": "Chat Type", "field": "chat_type", "align": "left"},
        ]
        rows = [
            {
                "time": format_timestamp(c.timestamp),
                "command": c.command,
                "username": c.username,
                "args": c.args or "-",
                "chat_type": c.chat_type,
            }
            for c in recent_commands
        ]
        ui.table(columns=columns, rows=rows, row_key="time").classes("w-full")


@ui.page("/users")
def users_page():
    """Users management page."""
    if not check_auth():
        return ui.navigate.to("/login")

    def refresh_table():
        users = User.select().order_by(User.id.desc())
        rows = [
            {
                "id": u.id,
                "telegram_id": u.telegram_id,
                "telegram_username": u.telegram_username or "-",
                "lastfm_username": u.lastfm_username or "-",
            }
            for u in users
        ]
        table.rows = rows
        table.update()

    def delete_user(user_id: int):
        User.delete().where(User.id == user_id).execute()
        ui.notify(f"User {user_id} deleted", type="positive")
        refresh_table()

    with ui.header().classes("bg-blue-600"):
        ui.label("LastfmBucket Admin").classes("text-xl text-white font-bold")
        ui.space()
        with ui.row():
            ui.button("Dashboard", on_click=lambda: ui.navigate.to("/")).props("flat color=white")
            ui.button("Users", on_click=lambda: ui.navigate.to("/users")).props("flat color=white")
            ui.button("Chats", on_click=lambda: ui.navigate.to("/chats")).props("flat color=white")
            ui.button("Command Logs", on_click=lambda: ui.navigate.to("/logs")).props(
                "flat color=white"
            )
            ui.button(
                "Logout",
                on_click=lambda: (app.storage.user.clear(), ui.navigate.to("/login")),
            ).props("flat color=white")

    with ui.column().classes("w-full p-4"):
        ui.label("Users").classes("text-2xl font-bold mb-4")

        columns = [
            {"name": "id", "label": "ID", "field": "id", "align": "left"},
            {"name": "telegram_id", "label": "Telegram ID", "field": "telegram_id", "align": "left"},
            {
                "name": "telegram_username",
                "label": "Telegram Username",
                "field": "telegram_username",
                "align": "left",
            },
            {
                "name": "lastfm_username",
                "label": "Last.fm Username",
                "field": "lastfm_username",
                "align": "left",
            },
            {"name": "actions", "label": "Actions", "field": "actions", "align": "center"},
        ]

        users = User.select().order_by(User.id.desc())
        rows = [
            {
                "id": u.id,
                "telegram_id": u.telegram_id,
                "telegram_username": u.telegram_username or "-",
                "lastfm_username": u.lastfm_username or "-",
            }
            for u in users
        ]

        table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")
        table.add_slot(
            "body-cell-actions",
            """
            <q-td :props="props">
                <q-btn flat color="negative" icon="delete" size="sm" 
                       @click="$parent.$emit('delete', props.row.id)" />
            </q-td>
        """,
        )
        table.on("delete", lambda e: delete_user(e.args))


@ui.page("/chats")
def chats_page():
    """Chats management page."""
    if not check_auth():
        return ui.navigate.to("/login")

    with ui.header().classes("bg-blue-600"):
        ui.label("LastfmBucket Admin").classes("text-xl text-white font-bold")
        ui.space()
        with ui.row():
            ui.button("Dashboard", on_click=lambda: ui.navigate.to("/")).props("flat color=white")
            ui.button("Users", on_click=lambda: ui.navigate.to("/users")).props("flat color=white")
            ui.button("Chats", on_click=lambda: ui.navigate.to("/chats")).props("flat color=white")
            ui.button("Command Logs", on_click=lambda: ui.navigate.to("/logs")).props(
                "flat color=white"
            )
            ui.button(
                "Logout",
                on_click=lambda: (app.storage.user.clear(), ui.navigate.to("/login")),
            ).props("flat color=white")

    with ui.column().classes("w-full p-4"):
        ui.label("Chats").classes("text-2xl font-bold mb-4")

        columns = [
            {"name": "id", "label": "ID", "field": "id", "align": "left"},
            {"name": "telegram_id", "label": "Telegram ID", "field": "telegram_id", "align": "left"},
            {
                "name": "telegram_chat_name",
                "label": "Chat Name",
                "field": "telegram_chat_name",
                "align": "left",
            },
        ]

        chats = Chat.select().order_by(Chat.id.desc())
        rows = [
            {
                "id": c.id,
                "telegram_id": c.telegram_id,
                "telegram_chat_name": c.telegram_chat_name or "-",
            }
            for c in chats
        ]

        ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")


@ui.page("/logs")
def logs_page():
    """Command logs page."""
    if not check_auth():
        return ui.navigate.to("/login")

    with ui.header().classes("bg-blue-600"):
        ui.label("LastfmBucket Admin").classes("text-xl text-white font-bold")
        ui.space()
        with ui.row():
            ui.button("Dashboard", on_click=lambda: ui.navigate.to("/")).props("flat color=white")
            ui.button("Users", on_click=lambda: ui.navigate.to("/users")).props("flat color=white")
            ui.button("Chats", on_click=lambda: ui.navigate.to("/chats")).props("flat color=white")
            ui.button("Command Logs", on_click=lambda: ui.navigate.to("/logs")).props(
                "flat color=white"
            )
            ui.button(
                "Logout",
                on_click=lambda: (app.storage.user.clear(), ui.navigate.to("/login")),
            ).props("flat color=white")

    with ui.column().classes("w-full p-4"):
        ui.label("Command Logs").classes("text-2xl font-bold mb-4")

        # Filters
        with ui.row().classes("gap-4 mb-4"):
            command_filter = ui.input("Filter by command").classes("w-48")
            user_filter = ui.input("Filter by username").classes("w-48")

            def apply_filters():
                query = CommandLog.select().order_by(CommandLog.timestamp.desc())
                if command_filter.value:
                    query = query.where(CommandLog.command.contains(command_filter.value))
                if user_filter.value:
                    query = query.where(CommandLog.username.contains(user_filter.value))
                query = query.limit(100)

                rows = [
                    {
                        "time": format_timestamp(c.timestamp),
                        "command": c.command,
                        "username": c.username or "-",
                        "args": c.args or "-",
                        "chat_type": c.chat_type,
                        "chat_id": c.chat_id,
                    }
                    for c in query
                ]
                table.rows = rows
                table.update()

            ui.button("Filter", on_click=apply_filters).props("color=primary")
            ui.button("Clear", on_click=lambda: (
                command_filter.set_value(""),
                user_filter.set_value(""),
                apply_filters(),
            )).props("color=secondary")

        columns = [
            {"name": "time", "label": "Time", "field": "time", "align": "left", "sortable": True},
            {
                "name": "command",
                "label": "Command",
                "field": "command",
                "align": "left",
                "sortable": True,
            },
            {
                "name": "username",
                "label": "Username",
                "field": "username",
                "align": "left",
                "sortable": True,
            },
            {"name": "args", "label": "Args", "field": "args", "align": "left"},
            {
                "name": "chat_type",
                "label": "Chat Type",
                "field": "chat_type",
                "align": "left",
                "sortable": True,
            },
            {"name": "chat_id", "label": "Chat ID", "field": "chat_id", "align": "left"},
        ]

        logs = CommandLog.select().order_by(CommandLog.timestamp.desc()).limit(100)
        rows = [
            {
                "time": format_timestamp(c.timestamp),
                "command": c.command,
                "username": c.username or "-",
                "args": c.args or "-",
                "chat_type": c.chat_type,
                "chat_id": c.chat_id,
            }
            for c in logs
        ]

        table = ui.table(columns=columns, rows=rows, row_key="time", pagination=20).classes(
            "w-full"
        )


def run_admin():
    """Run the admin server."""
    print(f"Starting admin dashboard on http://0.0.0.0:{ADMIN_PORT}")
    print(f"Login with username: {ADMIN_USERNAME}")
    ui.run(
        host="0.0.0.0",
        port=ADMIN_PORT,
        title="LastfmBucket Admin",
        storage_secret=ADMIN_SECRET_KEY,
        show=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    run_admin()
