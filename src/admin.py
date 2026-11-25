"""
Admin dashboard for LastfmBucket Bot using NiceGUI.

Provides a modern web interface to view and manage database models.
"""

from collections.abc import Callable
import datetime
import logging
import math
import os
import secrets
import time

from nicegui import Client, app, ui
from peewee import JOIN

import config
from db import Chat, ChatMember, CommandLog, Crown, User

logger = logging.getLogger(__name__)

# Configuration from centralized config (which loads .env)
ADMIN_USERNAME = config.ADMIN_USERNAME
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
ADMIN_PORT = config.ADMIN_PORT
ADMIN_SECRET_KEY = config.ADMIN_SECRET_KEY

# Store for authenticated sessions
app.storage.secret = ADMIN_SECRET_KEY


def is_weak_password(password: str | None) -> bool:
    """Return True if the password is empty or matches the insecure default."""
    normalized = (password or "").strip()
    return normalized == "" or password == "changeme"


def warn_if_weak_password(
    password: str | None, log: logging.Logger | None = None
) -> bool:
    """Log a prominent warning if ADMIN_PASSWORD is empty or default."""
    target_log = log or logger
    if is_weak_password(password):
        target_log.warning(
            "SECURITY WARNING: ADMIN_PASSWORD is weak or empty. "
            "Set a strong ADMIN_PASSWORD in your environment before exposing "
            "the admin dashboard."
        )
        return True
    return False


def verify_credentials(
    username: str | None,
    password: str | None,
    expected_username: str | None = None,
    expected_password: str | None = None,
) -> bool:
    """Verify username and password in constant time without short-circuiting."""
    target_user = ADMIN_USERNAME if expected_username is None else expected_username
    target_pass = ADMIN_PASSWORD if expected_password is None else expected_password

    user_ok = secrets.compare_digest(
        (username or "").encode("utf-8"), target_user.encode("utf-8")
    )
    pass_ok = secrets.compare_digest(
        (password or "").encode("utf-8"), target_pass.encode("utf-8")
    )
    return user_ok and pass_ok


class LoginRateLimiter:
    """In-memory per-client sliding-window brute-force rate limiter."""

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 300,
        lockout_seconds: int = 300,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._clock = clock
        self._attempts: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}

    def is_locked(self, key: str) -> tuple[bool, int]:
        """Return (is_locked, remaining_seconds) for the given client key."""
        now = self._clock()
        locked_until = self._locked_until.get(key)
        if locked_until is None:
            return False, 0

        if now < locked_until:
            remaining = max(1, math.ceil(locked_until - now))
            return True, remaining

        # Lockout expired; clear old attempts so client gets a fresh window.
        self._locked_until.pop(key, None)
        self._attempts.pop(key, None)
        return False, 0

    def _prune_expired(self, now: float) -> None:
        """Evict expired entries when tracking maps grow large."""
        if len(self._attempts) < 512 and len(self._locked_until) < 512:
            return
        for k, until in list(self._locked_until.items()):
            if now >= until:
                self._locked_until.pop(k, None)
                self._attempts.pop(k, None)
        for k, timestamps in list(self._attempts.items()):
            if k in self._locked_until:
                continue
            recent = [ts for ts in timestamps if now - ts < self.window_seconds]
            if recent:
                self._attempts[k] = recent
            else:
                self._attempts.pop(k, None)

    def record_failure(self, key: str) -> tuple[bool, int]:
        """Record a failed login attempt and return (is_locked, remaining_seconds)."""
        locked, remaining = self.is_locked(key)
        if locked:
            return True, remaining

        now = self._clock()
        self._prune_expired(now)
        recent = [
            ts for ts in self._attempts.get(key, []) if now - ts < self.window_seconds
        ]
        recent.append(now)
        self._attempts[key] = recent

        if len(recent) >= self.max_attempts:
            self._locked_until[key] = now + self.lockout_seconds
            return True, max(1, math.ceil(self.lockout_seconds))

        return False, 0

    def record_success(self, key: str) -> None:
        """Clear failure history and any lockout for the given client key."""
        self._attempts.pop(key, None)
        self._locked_until.pop(key, None)

    def reset(self) -> None:
        """Reset all tracked attempts and lockouts."""
        self._attempts.clear()
        self._locked_until.clear()


login_rate_limiter = LoginRateLimiter()


def get_client_rate_limit_key(client: Client | None = None) -> str:
    """Resolve a stable rate-limit key from client IP, forwarded headers, or browser."""
    if client is not None:
        try:
            request = getattr(client, "request", None)
        except RuntimeError:
            request = None
        if request is not None:
            headers = getattr(request, "headers", None)
            if headers:
                xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
                if xff:
                    first_ip = xff.split(",")[0].strip()
                    if first_ip:
                        return first_ip
        ip = getattr(client, "ip", None)
        if ip:
            return str(ip)

    try:
        browser_id = app.storage.browser.get("id")
        if browser_id:
            return f"browser:{browser_id}"
    except (RuntimeError, AttributeError):
        pass

    return "anonymous"


def check_auth() -> bool:
    """Check if user is authenticated."""
    return bool(app.storage.user.get("authenticated", False))


def format_timestamp(ts: int | None) -> str:
    """Format Unix timestamp to readable string, returning '-' when missing."""
    if ts is None or ts <= 0:
        return "-"
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def get_dashboard_stats() -> dict[str, int]:
    """Return summary counts for the admin dashboard."""
    today_start = int(
        datetime.datetime.now()
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    )
    return {
        "total_users": User.select().count(),
        "linked_users": User.select()
        .where((User.lastfm_username != "") & User.lastfm_username.is_null(False))
        .count(),
        "total_chats": Chat.select().count(),
        "total_crowns": Crown.select().count(),
        "total_commands": CommandLog.select().count(),
        "commands_today": CommandLog.select()
        .where(CommandLog.timestamp >= today_start)
        .count(),
    }


def fetch_command_log_rows(
    limit: int = 100, command_filter: str = "", user_filter: str = ""
) -> list[dict]:
    """Fetch command logs joined with Chat in a single query."""
    query = (
        CommandLog.select(CommandLog, Chat)
        .join(Chat, JOIN.LEFT_OUTER)
        .order_by(CommandLog.timestamp.desc(), CommandLog.id.desc())
    )
    if command_filter:
        query = query.where(CommandLog.command.contains(command_filter))
    if user_filter:
        query = query.where(CommandLog.username.contains(user_filter))
    query = query.limit(limit)

    rows: list[dict] = []
    for c in query:
        chat = c.__rel__.get("chat") if c.chat_id is not None else None
        rows.append(
            {
                "id": c.id,
                "time": format_timestamp(c.timestamp),
                "command": c.command,
                "username": c.username or "-",
                "args": c.args or "-",
                "chat_name": (chat.telegram_chat_name or "-") if chat else "-",
                "chat_type": (chat.chat_type or "-") if chat else "-",
            }
        )
    return rows


def fetch_crown_rows(
    artist_filter: str = "", chat_filter: str = "", limit: int = 200
) -> list[dict]:
    """Fetch crown records joined with Chat and User in a single query."""
    query = (
        Crown.select(Crown, Chat, User)
        .join(Chat, JOIN.LEFT_OUTER)
        .switch(Crown)
        .join(User, JOIN.LEFT_OUTER)
        .order_by(Crown.updated_at.desc(), Crown.id.desc())
    )
    if artist_filter:
        query = query.where(Crown.artist_name.contains(artist_filter))
    if chat_filter:
        query = query.where(Chat.telegram_chat_name.contains(chat_filter))
    query = query.limit(limit)

    rows: list[dict] = []
    for crown in query:
        chat = crown.__rel__.get("chat") if crown.chat_id is not None else None
        user = crown.__rel__.get("user") if crown.user_id is not None else None
        if user is None:
            holder = "-"
        else:
            holder = (
                user.telegram_username or user.lastfm_username or str(user.telegram_id)
            )
        rows.append(
            {
                "id": crown.id,
                "chat_name": (chat.telegram_chat_name or "-") if chat else "-",
                "artist_name": crown.artist_name,
                "holder": holder,
                "playcount": crown.playcount,
                "updated_at": format_timestamp(crown.updated_at),
            }
        )
    return rows


def fetch_chat_member_rows(
    chat_filter: str = "", user_filter: str = "", limit: int = 200
) -> list[dict]:
    """Fetch chat member records joined with Chat and User in a single query."""
    query = (
        ChatMember.select(ChatMember, Chat, User)
        .join(Chat, JOIN.LEFT_OUTER)
        .switch(ChatMember)
        .join(User, JOIN.LEFT_OUTER)
        .order_by(ChatMember.last_active.desc(), ChatMember.id.desc())
    )
    if chat_filter:
        query = query.where(Chat.telegram_chat_name.contains(chat_filter))
    if user_filter:
        query = query.where(
            User.telegram_username.contains(user_filter)
            | User.lastfm_username.contains(user_filter)
        )
    query = query.limit(limit)

    rows: list[dict] = []
    for member in query:
        chat = member.__rel__.get("chat") if member.chat_id is not None else None
        user = member.__rel__.get("user") if member.user_id is not None else None
        rows.append(
            {
                "id": member.id,
                "chat_name": (chat.telegram_chat_name or "-") if chat else "-",
                "telegram_username": (user.telegram_username or "-") if user else "-",
                "lastfm_username": (user.lastfm_username or "-") if user else "-",
                "last_active": format_timestamp(member.last_active),
                "opt_out": "Yes" if member.opt_out else "No",
            }
        )
    return rows


def fetch_user_rows() -> list[dict]:
    """Fetch user records formatted for the Users table."""
    users = User.select().order_by(User.id.desc())
    return [
        {
            "id": u.id,
            "telegram_id": u.telegram_id,
            "telegram_username": u.telegram_username or "-",
            "lastfm_username": u.lastfm_username or "-",
            "group_opt_out": "Yes" if u.group_opt_out else "No",
        }
        for u in users
    ]


def delete_user_by_id(user_id: int) -> int:
    """Delete a user record by primary key."""
    return User.delete().where(User.id == user_id).execute()


def delete_crown_by_id(crown_id: int) -> int:
    """Delete a crown record by primary key."""
    return Crown.delete().where(Crown.id == crown_id).execute()


def render_nav_header(active_path: str = "") -> None:
    """Render the shared navigation header across authenticated pages."""
    nav_items = [
        ("/", "Dashboard"),
        ("/users", "Users"),
        ("/chats", "Chats"),
        ("/logs", "Command Logs"),
        ("/crowns", "Crowns"),
        ("/members", "Members"),
    ]
    with ui.header().classes("bg-blue-600"):
        ui.label("LastfmBucket Admin").classes("text-xl text-white font-bold")
        ui.space()
        with ui.row().classes("gap-1"):
            for path, label in nav_items:
                btn = ui.button(
                    label, on_click=lambda target=path: ui.navigate.to(target)
                ).props("flat color=white")
                if active_path == path:
                    btn.classes("bg-blue-700 underline")
            ui.button(
                "Logout",
                on_click=lambda: (app.storage.user.clear(), ui.navigate.to("/login")),
            ).props("flat color=white")


def open_confirm_dialog(
    title: str, message: str, on_confirm: Callable[[], None]
) -> None:
    """Open a modal confirmation dialog before performing a destructive action."""
    with ui.dialog() as dialog, ui.card():
        ui.label(title).classes("text-lg font-bold")
        ui.label(message).classes("text-sm text-gray-700 my-2")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):

            def handle_cancel():
                dialog.close()
                dialog.delete()

            ui.button("Cancel", on_click=handle_cancel).props("flat")

            def handle_confirm():
                dialog.close()
                dialog.delete()
                on_confirm()

            ui.button("Confirm Delete", on_click=handle_confirm).props("color=negative")
    dialog.open()


@ui.page("/login")
def login_page(client: Client):
    """Login page."""

    def try_login():
        rate_key = get_client_rate_limit_key(client)
        locked, remaining = login_rate_limiter.is_locked(rate_key)
        if locked:
            ui.notify(
                f"Too many failed login attempts. Try again in {remaining}s.",
                type="negative",
            )
            return

        if verify_credentials(username.value, password.value):
            login_rate_limiter.record_success(rate_key)
            app.storage.user["authenticated"] = True
            ui.navigate.to("/")
        else:
            locked, remaining = login_rate_limiter.record_failure(rate_key)
            if locked:
                ui.notify(
                    f"Too many failed login attempts. Try again in {remaining}s.",
                    type="negative",
                )
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

    render_nav_header("/")

    stats = get_dashboard_stats()
    stat_cards = [
        ("Total Users", stats["total_users"], "bg-blue-500"),
        ("Linked Users", stats["linked_users"], "bg-indigo-500"),
        ("Total Chats", stats["total_chats"], "bg-green-500"),
        ("Total Crowns", stats["total_crowns"], "bg-amber-600"),
        ("Total Commands", stats["total_commands"], "bg-purple-500"),
        ("Commands Today", stats["commands_today"], "bg-orange-500"),
    ]

    with ui.column().classes("w-full p-4"):
        ui.label("Dashboard").classes("text-2xl font-bold mb-4")

        # Stats cards
        with ui.row().classes("w-full gap-4 flex-wrap"):
            for title, value, color_cls in stat_cards:
                with ui.card().classes(f"{color_cls} text-white"):
                    ui.label(title).classes("text-sm opacity-80")
                    ui.label(str(value)).classes("text-3xl font-bold")

        # Recent commands
        ui.label("Recent Commands").classes("text-xl font-bold mt-6 mb-2")
        columns = [
            {"name": "time", "label": "Time", "field": "time", "align": "left"},
            {
                "name": "command",
                "label": "Command",
                "field": "command",
                "align": "left",
            },
            {"name": "username", "label": "User", "field": "username", "align": "left"},
            {"name": "args", "label": "Args", "field": "args", "align": "left"},
            {
                "name": "chat_name",
                "label": "Chat",
                "field": "chat_name",
                "align": "left",
            },
            {
                "name": "chat_type",
                "label": "Type",
                "field": "chat_type",
                "align": "left",
            },
        ]
        rows = fetch_command_log_rows(limit=10)
        ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")


@ui.page("/users")
def users_page():
    """Users management page."""
    if not check_auth():
        return ui.navigate.to("/login")

    def refresh_table():
        table.rows = fetch_user_rows()
        table.update()

    def confirm_delete_user(user_id: int):
        def perform_delete():
            delete_user_by_id(user_id)
            ui.notify(f"User {user_id} deleted", type="positive")
            refresh_table()

        open_confirm_dialog(
            title="Confirm User Deletion",
            message=(
                f"Delete user {user_id}? This permanently removes the user and "
                "cascades to their chat memberships and crowns."
            ),
            on_confirm=perform_delete,
        )

    render_nav_header("/users")

    with ui.column().classes("w-full p-4"):
        ui.label("Users").classes("text-2xl font-bold mb-4")

        columns = [
            {"name": "id", "label": "ID", "field": "id", "align": "left"},
            {
                "name": "telegram_id",
                "label": "Telegram ID",
                "field": "telegram_id",
                "align": "left",
            },
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
            {
                "name": "group_opt_out",
                "label": "Opt Out",
                "field": "group_opt_out",
                "align": "center",
            },
            {
                "name": "actions",
                "label": "Actions",
                "field": "actions",
                "align": "center",
            },
        ]

        table = ui.table(columns=columns, rows=fetch_user_rows(), row_key="id").classes(
            "w-full"
        )
        table.add_slot(
            "body-cell-actions",
            """
            <q-td :props="props">
                <q-btn flat color="negative" icon="delete" size="sm"
                       @click="$parent.$emit('delete', props.row.id)" />
            </q-td>
        """,
        )
        table.on("delete", lambda e: confirm_delete_user(e.args))


@ui.page("/chats")
def chats_page():
    """Chats management page."""
    if not check_auth():
        return ui.navigate.to("/login")

    render_nav_header("/chats")

    with ui.column().classes("w-full p-4"):
        ui.label("Chats").classes("text-2xl font-bold mb-4")

        columns = [
            {"name": "id", "label": "ID", "field": "id", "align": "left"},
            {
                "name": "telegram_id",
                "label": "Telegram ID",
                "field": "telegram_id",
                "align": "left",
            },
            {
                "name": "telegram_chat_name",
                "label": "Chat Name",
                "field": "telegram_chat_name",
                "align": "left",
            },
            {
                "name": "chat_type",
                "label": "Type",
                "field": "chat_type",
                "align": "left",
            },
        ]

        chats = Chat.select().order_by(Chat.id.desc())
        rows = [
            {
                "id": c.id,
                "telegram_id": c.telegram_id,
                "telegram_chat_name": c.telegram_chat_name or "-",
                "chat_type": c.chat_type or "-",
            }
            for c in chats
        ]

        ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")


@ui.page("/logs")
def logs_page():
    """Command logs page."""
    if not check_auth():
        return ui.navigate.to("/login")

    render_nav_header("/logs")

    with ui.column().classes("w-full p-4"):
        ui.label("Command Logs").classes("text-2xl font-bold mb-4")

        # Filters
        with ui.row().classes("gap-4 mb-4"):
            command_filter = ui.input("Filter by command").classes("w-48")
            user_filter = ui.input("Filter by username").classes("w-48")

            def apply_filters():
                table.rows = fetch_command_log_rows(
                    limit=100,
                    command_filter=command_filter.value or "",
                    user_filter=user_filter.value or "",
                )
                table.update()

            ui.button("Filter", on_click=apply_filters).props("color=primary")
            ui.button(
                "Clear",
                on_click=lambda: (
                    command_filter.set_value(""),
                    user_filter.set_value(""),
                    apply_filters(),
                ),
            ).props("color=secondary")

        columns = [
            {
                "name": "time",
                "label": "Time",
                "field": "time",
                "align": "left",
                "sortable": True,
            },
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
                "name": "chat_name",
                "label": "Chat",
                "field": "chat_name",
                "align": "left",
            },
            {
                "name": "chat_type",
                "label": "Type",
                "field": "chat_type",
                "align": "left",
                "sortable": True,
            },
        ]

        table = ui.table(
            columns=columns,
            rows=fetch_command_log_rows(limit=100),
            row_key="id",
            pagination=20,
        ).classes("w-full")


@ui.page("/crowns")
def crowns_page():
    """Group crowns management page."""
    if not check_auth():
        return ui.navigate.to("/login")

    render_nav_header("/crowns")

    with ui.column().classes("w-full p-4"):
        ui.label("Group Crowns").classes("text-2xl font-bold mb-4")

        with ui.row().classes("gap-4 mb-4"):
            artist_filter = ui.input("Filter by artist").classes("w-48")
            chat_filter = ui.input("Filter by chat").classes("w-48")

            def apply_filters():
                table.rows = fetch_crown_rows(
                    artist_filter=artist_filter.value or "",
                    chat_filter=chat_filter.value or "",
                )
                table.update()

            ui.button("Filter", on_click=apply_filters).props("color=primary")
            ui.button(
                "Clear",
                on_click=lambda: (
                    artist_filter.set_value(""),
                    chat_filter.set_value(""),
                    apply_filters(),
                ),
            ).props("color=secondary")

        def confirm_delete_crown(crown_id: int):
            def perform_delete():
                delete_crown_by_id(crown_id)
                ui.notify(f"Crown {crown_id} deleted", type="positive")
                apply_filters()

            open_confirm_dialog(
                title="Confirm Crown Deletion",
                message=f"Delete crown {crown_id}? This action cannot be undone.",
                on_confirm=perform_delete,
            )

        columns = [
            {
                "name": "chat_name",
                "label": "Chat",
                "field": "chat_name",
                "align": "left",
                "sortable": True,
            },
            {
                "name": "artist_name",
                "label": "Artist",
                "field": "artist_name",
                "align": "left",
                "sortable": True,
            },
            {
                "name": "holder",
                "label": "Holder",
                "field": "holder",
                "align": "left",
                "sortable": True,
            },
            {
                "name": "playcount",
                "label": "Playcount",
                "field": "playcount",
                "align": "right",
                "sortable": True,
            },
            {
                "name": "updated_at",
                "label": "Updated",
                "field": "updated_at",
                "align": "left",
                "sortable": True,
            },
            {
                "name": "actions",
                "label": "Actions",
                "field": "actions",
                "align": "center",
            },
        ]

        table = ui.table(
            columns=columns, rows=fetch_crown_rows(), row_key="id", pagination=20
        ).classes("w-full")
        table.add_slot(
            "body-cell-actions",
            """
            <q-td :props="props">
                <q-btn flat color="negative" icon="delete" size="sm"
                       @click="$parent.$emit('delete', props.row.id)" />
            </q-td>
        """,
        )
        table.on("delete", lambda e: confirm_delete_crown(e.args))


@ui.page("/members")
def members_page():
    """Chat members inspection page."""
    if not check_auth():
        return ui.navigate.to("/login")

    render_nav_header("/members")

    with ui.column().classes("w-full p-4"):
        ui.label("Chat Members").classes("text-2xl font-bold mb-4")

        with ui.row().classes("gap-4 mb-4"):
            chat_filter = ui.input("Filter by chat").classes("w-48")
            user_filter = ui.input("Filter by username").classes("w-48")

            def apply_filters():
                table.rows = fetch_chat_member_rows(
                    chat_filter=chat_filter.value or "",
                    user_filter=user_filter.value or "",
                )
                table.update()

            ui.button("Filter", on_click=apply_filters).props("color=primary")
            ui.button(
                "Clear",
                on_click=lambda: (
                    chat_filter.set_value(""),
                    user_filter.set_value(""),
                    apply_filters(),
                ),
            ).props("color=secondary")

        columns = [
            {
                "name": "chat_name",
                "label": "Chat",
                "field": "chat_name",
                "align": "left",
                "sortable": True,
            },
            {
                "name": "telegram_username",
                "label": "Telegram Username",
                "field": "telegram_username",
                "align": "left",
                "sortable": True,
            },
            {
                "name": "lastfm_username",
                "label": "Last.fm Username",
                "field": "lastfm_username",
                "align": "left",
                "sortable": True,
            },
            {
                "name": "last_active",
                "label": "Last Active",
                "field": "last_active",
                "align": "left",
                "sortable": True,
            },
            {
                "name": "opt_out",
                "label": "Opt Out",
                "field": "opt_out",
                "align": "center",
                "sortable": True,
            },
        ]

        table = ui.table(
            columns=columns, rows=fetch_chat_member_rows(), row_key="id", pagination=20
        ).classes("w-full")


def run_admin():
    """Run the admin server."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    warn_if_weak_password(ADMIN_PASSWORD)
    logger.info("Starting admin dashboard on http://0.0.0.0:%s", ADMIN_PORT)
    logger.info("Login with username: %s", ADMIN_USERNAME)
    ui.run(
        host="0.0.0.0",
        port=ADMIN_PORT,
        title="LastfmBucket Admin",
        storage_secret=ADMIN_SECRET_KEY,
        show=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    run_admin()
