# Proposal

## Why

Production usage and code review of `lastfmbucket-bot` uncovered multiple stability, security, data-integrity, and UX bugs across command handlers, inline callbacks, Last.fm validation, and SQLite persistence: unescaped HTML causes guaranteed Telegram `BadRequest` crashes on `/set`, `/compare`, and special-character artist/track metadata; inline callbacks lack user ownership checks, double-answer queries, can exceed Telegram's 64-byte limit, and crash when converting text messages to photos; Last.fm lookups do not validate users or artists against the API; SQLite durability (`synchronous=0`) and chat metadata updates risk corruption/data loss; and privacy controls leave command logs behind while sending PII to Sentry. Fixing these issues now stabilizes production behavior, closes cross-user button hijacking, aligns privacy behavior with policy, and brings the bot into compliance with its existing specifications.

## What Changes

- **HTML Safety & `ParseMode.HTML` Fixes**:
  - Escape angle brackets in `/set` and `/compare` usage messages (`src/commands.py`) so invoking them without arguments no longer raises Telegram `BadRequest`.
  - Escape all dynamic user, Last.fm, changelog, and error text with `html.escape()` across `src/services.py` and `src/commands.py`.
- **Callback Security, Reliability & Compact Encoding**:
  - Enforce `query.from_user.id == cb.owner_id` ownership checks in `button_handler` for all user-scoped actions (`PREF_UNLINK`, `PREF_OPT_OUT`, `COLLAGE`, `TOPS`, `NP_LESS`, `NP_LESS_COVER`, `NP_MORE`), responding with an alert (`show_alert=True`) on unauthorized clicks while keeping `Action.WHOKNOWS` open to all group members.
  - Eliminate duplicate `query.answer()` calls so alert responses are delivered reliably.
  - Guard `status` media updates with `if cover_url:` and safely handle text-to-photo transitions in both `now_playing` and `status` (send new photo and delete old text message when the original message has no media, or edit media/caption when it already has a photo).
  - Replace the production `assert` in `Callback.encode()` with an explicit `ValueError`, and encode theme, overlay, preset, and style values with compact short codes so 64-bit Telegram user IDs stay well under Telegram's 64-byte callback limit while preserving backwards-compatible decoding of legacy payloads.
- **Last.fm API Validation Fixes**:
  - Make `LastfmClient.get_user()` perform a real Last.fm lookup and return `None` on `pylast.WSError` / missing users instead of returning an unvalidated `pylast.User` handle.
  - Pass `properly_capitalized=True` in `LastfmClient.get_artist_canonical_info()` so Last.fm validates artist existence and returns canonical casing, returning `None` when not found.
- **Database Durability, Integrity, Indexing & Privacy Deletion**:
  - Set SQLite `synchronous` pragma to `1` (`NORMAL`, safe with WAL mode) in `src/db.py`.
  - Prevent `db.get_or_create_chat()` (and by extension `upsert_crown()`) from overwriting existing non-empty `telegram_chat_name` or `chat_type` with empty strings.
  - Add SQLite indexes on `CommandLog` (`timestamp`, `user_id`, `command`) in the Peewee model and idempotently in `run_migrations()`.
  - Update `db.delete_user()` so unlinking an account also deletes `CommandLog` rows for that `telegram_user_id`.
- **Privacy & Sentry Alignment**:
  - Set `send_default_pii=False` in `sentry_sdk.init(...)` in `src/bot.py`.
  - Update `/privacy` copy in `src/responses.py` to accurately document stored data and the `/preferences` -> Unlink deletion flow.
- **UX, Spec Compliance & Language Consistency**:
  - Handle `telegram_user.username is None` in `/start` (fallback to escaped `first_name` or `"there"` instead of `Hi @None`).
  - Distinguish linked users with zero recent tracks in `/status` from unlinked users by returning a dedicated empty-tracks message.
  - Truncate `/crowns` user showcase responses cleanly before Telegram's 4096-character limit with a `... and N more crowns` footer.
  - Delete the `"Generating..."` status message in `finally` for the interactive `/collage` wizard and clarify the confirm button label (`"✨ Skip & Generate"` / `"✅ Generate"`).
  - Register a passive group `MessageHandler` in `src/bot.py` (`filters.ChatType.GROUPS & ~filters.COMMAND`) to auto-discover linked `ChatMember`s on regular group messages without creating placeholder rows for bots or unlinked users.
  - Unify mixed Catalan/English UI strings in `src/services.py` and `src/responses.py` to consistent English, update affected existing tests in `src/tests.py`, and add a dedicated regression suite in `tests/test_stability_security.py`.

## Capabilities

### New Capabilities
<!-- None; all changes strengthen or refine existing capabilities. -->

### Modified Capabilities
- `bot-command-handlers`: Enforce strict HTML escaping across all dynamic command/service outputs, add callback ownership validation with single `query.answer()` semantics, fix text-to-photo media transitions, compact callback encoding under 64 bytes, validate Last.fm users via real API calls, handle missing Telegram usernames in `/start` and empty history in `/status`, and unify UI copy to English.
- `telegram-bot-core`: Disable Sentry PII collection (`send_default_pii=False`), align `/privacy` policy with actual stored data and unlink deletion, harden SQLite durability (`synchronous=1`), preserve non-empty chat metadata, index `CommandLog`, and purge `CommandLog` rows on account deletion.
- `group-whoknows`: Add passive group message handler for linked `ChatMember` discovery, enforce real Last.fm artist canonicalization (`properly_capitalized=True`), escape all dynamic HTML fields, and standardize UI strings to English.
- `crowns-hall-of-fame`: Truncate `/crowns` user showcase messages within Telegram's 4096-character limit, preserve chat metadata on crown upserts, and standardize opt-out UI copy to English.
- `collage-generation`: Clean up interactive wizard status messages in `finally`, clarify the style-step generate button label, enforce callback ownership and compact 64-byte encoding, escape error/caption fields, and unify caption strings to English.

## Impact

- **Owned source files**: `src/bot.py`, `src/commands.py`, `src/callbacks.py`, `src/lastfm.py`, `src/db.py`, `src/responses.py`, `src/services.py`.
- **Tests**: Update affected English-string assertions in `src/tests.py` and add comprehensive unit tests in `tests/test_stability_security.py`.
- **Database**: Backward-compatible schema migration adds indexes on `commandlog` (`timestamp`, `user_id`, `command`) via `CREATE INDEX IF NOT EXISTS`; no destructive schema changes.
- **Callbacks**: New compact short codes for collage style fields remain backward-compatible with previously sent inline keyboards via `Callback.decode()`.
- **Out of scope**: Async/event-loop/AI/performance optimizations (`optimize-bot-concurrency-and-ai`), `src/admin.py`, `Dockerfile`, `pyproject.toml`, and `src/config.py`.
