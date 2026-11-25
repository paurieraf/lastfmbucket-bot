# Design

## Context

`lastfmbucket-bot` uses `python-telegram-bot` 22.8 with global `Defaults(parse_mode=ParseMode.HTML)`, Peewee + `SqliteExtDatabase` in WAL mode, `pylast` for Last.fm API calls, and `sentry_sdk` for error tracking. See `proposal.md` for the full motivation and scope.

This design stays strictly within the stability/security file boundary (`src/bot.py`, `src/commands.py`, `src/callbacks.py`, `src/lastfm.py`, `src/db.py`, `src/responses.py`, `src/services.py`, `src/tests.py`, and `tests/test_stability_security.py`) and avoids overlapping with async/AI/concurrency optimizations in `optimize-bot-concurrency-and-ai` or infrastructure files (`admin.py`, `Dockerfile`, `pyproject.toml`, `config.py`).

## Goals / Non-Goals

**Goals:**
- Guarantee valid HTML output for every command, service view, changelog, and error message under `ParseMode.HTML`.
- Enforce strict callback ownership, single-answer semantics, safe text-to-photo transitions, and 64-byte-safe callback serialization.
- Ensure Last.fm user and artist lookups perform real API validation.
- Harden SQLite durability, preserve chat metadata, index `CommandLog`, and complete privacy deletion on unlink.
- Align Sentry PII settings and `/privacy` copy with actual behavior.
- Fix `/start`, `/status`, `/crowns`, interactive `/collage`, passive group discovery, and Catalan/English copy inconsistencies.

**Non-Goals:**
- Refactoring `LastfmClient` into async HTTP or optimizing AI/event-loop concurrency (`optimize-bot-concurrency-and-ai`).
- Modifying `src/admin.py`, `Dockerfile`, `pyproject.toml`, or `src/config.py`.
- Adding multi-language i18n infrastructure (all UI copy is standardized to English).

## Decisions

### 1. Centralized HTML Escaping at View/Handler Boundaries
- **Decision**: Escape all untrusted/dynamic values with `html.escape(val)` (and `html.escape(url, quote=True)` inside `href='...'` / `href="..."`) at every `Template.substitute(...)` call in `src/services.py` and error/usage replies in `src/commands.py`.
  - Fix `/set` and `/compare` usage strings using `<code>/set &lt;username&gt;</code>` and `<code>/compare &lt;lastfm_username&gt;</code>` (or `&lt;...&gt;`).
  - In `build_changelog_response()`, apply `html.escape()` before wrapping in `<pre>...</pre>`, truncating safely so the final HTML string stays under 4096 characters (accounting for entity expansion).
  - For URLs containing `lastfm_username` (`https://www.last.fm/user/{username}`), apply `urllib.parse.quote(username, safe="")` for the `href` attribute and `html.escape(username)` for the display label.
- **Alternative considered**: Switching commands to `ParseMode.NONE` on error replies. Rejected because global `Defaults(parse_mode=ParseMode.HTML)` is active everywhere and escaping consistently prevents regressions across all templates.

### 2. Callback Ownership Validation & Single `query.answer()` Lifecycle
- **Decision**:
  - Define `USER_SCOPED_ACTIONS = frozenset({Action.PREF_UNLINK, Action.PREF_OPT_OUT, Action.COLLAGE, Action.TOPS, Action.NP_LESS, Action.NP_LESS_COVER, Action.NP_MORE})`.
  - Remove the unconditional `await query.answer()` at the top of `button_handler`.
  - Decode `cb = Callback.decode(query.data or "")`. On invalid data, call `await query.answer("Invalid or expired button.")` and return.
  - If `cb.action in USER_SCOPED_ACTIONS` and `(not query.from_user or query.from_user.id != cb.owner_id)`: call `await query.answer("This button belongs to another user.", show_alert=True)` and return immediately.
  - For `Action.WHOKNOWS` (intentionally shared in groups), delegate answering to `_handle_whoknows_button`, which answers with `show_alert=True` on missing track or `await query.answer()` on success. For all other actions, `button_handler` calls `await query.answer()` once right before dispatching `await handler(update, context, cb)`.
- **Alternative considered**: Having every handler call `query.answer()`. Rejected because centralizing it in `button_handler` (with only `WHOKNOWS` owning its conditional alert) avoids forgotten answers while eliminating double-answer bugs.

### 3. Safe Text-to-Photo Media Transitions in `/np` and `/status`
- **Decision**: Extract a helper `_update_or_replace_with_media(message, response, reply_markup, cover_url)` in `src/commands.py` used by both `now_playing` and `status` when `from_button and show_cover`:
  - Determine `has_photo = bool(getattr(message, "photo", None))`.
  - If `cover_url`:
    - If `has_photo`: call `await message.edit_media(telegram.InputMediaPhoto(media=cover_url, caption=response), reply_markup=reply_markup)`.
    - Else (text-only message): call `await message.reply_photo(photo=cover_url, caption=response, reply_markup=reply_markup)` and then `try: await message.delete() except Exception: pass`.
  - Else (`cover_url` is `None`):
    - If `has_photo`: call `await message.edit_caption(caption=response, reply_markup=reply_markup)`.
    - Else: call `await message.edit_text(response, reply_markup=reply_markup)`.
- **Alternative considered**: Always sending a new photo without deleting the old message. Rejected because deleting the replaced text message avoids cluttering group chats, while tolerating delete failures (e.g. missing bot delete permission) gracefully.

### 4. Compact Callback Encoding with Legacy Backwards Compatibility
- **Decision**:
  - Replace `assert len(encoded.encode("utf-8")) <= 64` in `Callback.encode()` with `if len(encoded.encode("utf-8")) > 64: raise ValueError(...)`.
  - Add compact 1-character lookup tables in `src/callbacks.py`:
    - `THEME_TO_CODE = {"dark": "d", "light": "l", "glassmorphic": "g", "sunset": "s", "neon": "n", "adaptive": "a"}`
    - `OVERLAY_TO_CODE = {"banner": "b", "full_tint": "f", "gradient": "g", "pill": "p", "clean": "c"}`
    - `PRESET_TO_CODE = {"story": "s", "instagram-story": "s", "post": "p", "instagram-post": "p", "header": "h", "twitter-header": "h", "wallpaper": "w", "desktop-wallpaper": "w", "4k": "4", "desktop-wallpaper-4k": "4"}`
    - `STYLE_TO_CODE = {"set": "s", "skip": "k"}`
  - Encode fields using these short codes (unknown values fall back to raw string). Worst-case payload with 19-digit 64-bit `owner_id` (`1|cl|9223372036854775807|a|w|10x10|g|f|w|k`) is 42 bytes (22 bytes of headroom below 64).
  - In `Callback.decode()`, map short codes back via `CODE_TO_*` (returning canonical names like `"glassmorphic"`, `"full_tint"`, `"story"`, `"set"`, `"skip"`), and pass through legacy full strings unchanged so existing inline keyboards in chats keep working.
- **Alternative considered**: Bumping `VERSION` to `"2"` and dropping `"1"`. Rejected because in-place compact encoding within `"1"` with fallback decode supports both old and new buttons seamlessly without branching version parsers.

### 5. Real Last.fm API Validation
- **Decision**:
  - `LastfmClient.get_user(username)`: strip whitespace; return `None` if empty. Instantiate `user = self.client.get_user(clean_username)` and call `user.get_registered()` (lightweight `user.getInfo` call). Catch `pylast.WSError` (and unexpected exceptions, logged as warning) and return `None`.
  - `LastfmClient.get_artist_canonical_info(artist_name)`: strip whitespace; return `None` if empty. Call `artist.get_name(properly_capitalized=True)` which triggers `artist.getInfo` on Last.fm and raises `pylast.WSError` if the artist is not found. Return `None` on empty result or exception.
- **Alternative considered**: `user.get_playcount()`. Both `get_registered()` and `get_playcount()` hit `user.getInfo` in `pylast`; `get_registered()` is a clean existence check that works even for brand-new accounts with 0 scrobbles.

### 6. SQLite Durability, Metadata Preservation, Indexing & Privacy Deletion
- **Decision**:
  - Change `"synchronous": 0` to `"synchronous": 1` (`NORMAL`) in `src/db.py` (standard durability setting for WAL mode).
  - In `get_or_create_chat(telegram_chat_id, chat_name="", chat_type="")`: when `not created`, only update `chat.telegram_chat_name` if `chat_name` is truthy and differs, and only update `chat.chat_type` if `chat_type` is truthy and differs. Only call `chat.save()` when at least one field actually changed.
  - Add `index=True` on `CommandLog.user_id`, `CommandLog.command`, and `CommandLog.timestamp`. In `run_migrations()`, run `CREATE INDEX IF NOT EXISTS` for `idx_commandlog_timestamp`, `idx_commandlog_user_id`, and `idx_commandlog_command` on `commandlog`.
  - In `delete_user(telegram_user_id)`: inside the same `with db.atomic():` transaction, delete the `User` instance (which cascades `ChatMember` and `Crown`) and execute `CommandLog.delete().where(CommandLog.user_id == telegram_user_id).execute()`. Even if no `User` row exists (e.g., user ran commands before linking), still purge `CommandLog` rows for `telegram_user_id`.

### 7. Passive Group Membership Discovery
- **Decision**:
  - Add `async def track_group_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None` in `src/commands.py`.
  - Register it in `src/bot.py` via `app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, commands.track_group_member), group=1)` so it never interferes with command handlers in group `0`.
  - Inside `track_group_member`: return early if `not update.effective_user`, `not update.effective_chat`, or `update.effective_user.is_bot`. Check `db.get_linked_user(user.id)` — only call `db.track_chat_member(...)` if the user already has a linked Last.fm account. This satisfies `group-whoknows` auto-discovery while preventing DB bloat from unlinked group chatter or bots.
- **Alternative considered**: Tracking every group message regardless of linked status. Rejected because it would insert placeholder `User` and `ChatMember` rows for every unlinked member in every group, inflating the DB and storing data on users who never interacted with the bot.

### 8. UX Polish: `/start`, `/status`, `/crowns`, Interactive `/collage`, English Copy
- **Decision**:
  - `/start`: Update `responses.start_response` from `Hi @$username,` to `Hi $username,`. In `build_start_response()`, compute `f"@{html.escape(telegram_user.username)}"` if `username` else `html.escape(telegram_user.first_name)` if `first_name` else `"there"`.
  - `/status`: Check `if not user:` first (`user_not_found`), then fetch `recent_tracks`. If `not recent_tracks`, return a new `responses.recent_tracks_empty` template (`🔎 No recent tracks found for <b>$lastfm_username</b>.`).
  - `/crowns` showcase truncation: Build the header first, then append crown lines while `current_len + len(line) + 1 <= 3950` (leaving headroom for the footer and staying safely under Telegram's 4096-character limit). If truncated, append `\n\n<i>... and {remaining} more crowns</i>`.
  - Interactive `/collage`: Wrap generation in `try ... finally:` that deletes `query.message` (ignoring deletion errors), matching CLI `/collage`. Label the style-step confirmation button `"✅ Generate"` when `theme or overlay` is selected, and `"✨ Skip & Generate"` when neither is selected.
  - English copy: Replace all remaining Catalan UI strings in `src/services.py` (`"👑 Who knows?"`, `"🔒 Hide me from group rankings"`, `"🔓 Show me in group rankings"`, `"Hidden from group rankings 🔒"`, `"Visible in group rankings 🔓"`, `"no text"`, `"filter {filter_name}"`, `"⚔️ NEW BAND KING!"`) and update the single affected assertion in `src/tests.py`.

## Risks / Trade-offs

- **[Risk] Deleting the old text message on text-to-photo transition in groups without admin delete permissions** → Mitigation: Wrap `await message.delete()` in `try/except Exception: pass` so the new photo is always delivered even if deletion is disallowed.
- **[Risk] `LastfmClient.get_user()` adds one HTTP round-trip on `/set`** → Mitigation: `/set` is a rare user action and already runs off the event loop via `_run_lastfm_call`; real validation prevents storing typos/invalid usernames.
- **[Risk] Passive `MessageHandler` runs on every group message** → Mitigation: Early-return on bots and check `db.get_linked_user(user.id)` (indexed `telegram_id` unique lookup), writing only for linked users.
- **[Risk] Changing Catalan strings to English could break existing tests** → Mitigation: Update the affected test in `src/tests.py` (`test_collage_caption_with_style`) and verify both `src/tests.py` and `tests/test_stability_security.py` pass.

## Migration Plan

1. Deploy updated code; `db.create_tables(MODELS, safe=True)` and `run_migrations()` run automatically at import/startup, creating `CommandLog` indexes idempotently via `CREATE INDEX IF NOT EXISTS`.
2. Existing inline keyboards in Telegram chats continue decoding seamlessly through backwards-compatible `Callback.decode()`.
3. Rollback is a standard code revert; added SQLite indexes and `synchronous=1` are fully backward-compatible with previous versions.
