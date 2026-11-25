# Tasks

## 1. Database Durability, Integrity, Indexing & Privacy Deletion

- [x] 1.1 Update `src/db.py` pragmas (`"synchronous": 1`), preserve non-empty `telegram_chat_name` and `chat_type` in `get_or_create_chat()`, add `index=True` on `CommandLog` (`timestamp`, `user_id`, `command`) with idempotent `CREATE INDEX IF NOT EXISTS` migrations in `run_migrations()`, and update `delete_user()` to delete `CommandLog` rows for `telegram_user_id`; verify with unit tests in `tests/test_stability_security.py` covering `synchronous` pragma, `upsert_crown` preserving chat metadata, `run_migrations` creating `CommandLog` indexes on a legacy DB, and `delete_user` purging `CommandLog` rows.

## 2. Last.fm Validation Fixes

- [x] 2.1 Update `LastfmClient.get_user()` in `src/lastfm.py` to perform a real API lookup (`user.get_registered()`), returning `None` on empty username or `pylast.WSError`/error, and update `LastfmClient.get_artist_canonical_info()` to call `artist.get_name(properly_capitalized=True)` and return `None` when not found; verify with mocked `pylast` unit tests in `tests/test_stability_security.py`.

## 3. Compact Callback Protocol & Security

- [x] 3.1 Update `src/callbacks.py` to replace the `assert` in `Callback.encode()` with `ValueError`, add compact short-code mappings for `theme`, `overlay`, `preset`, and `style` so 64-bit `owner_id` payloads stay well under 64 bytes, and preserve backwards-compatible decoding of legacy full strings in `Callback.decode()`; verify with round-trip, overflow (`ValueError`), 64-bit ID length, and legacy-payload unit tests in `tests/test_stability_security.py`.
- [x] 3.2 Update `button_handler` and `_handle_whoknows_button` in `src/commands.py` to enforce `query.from_user.id == cb.owner_id` for user-scoped actions (`PREF_UNLINK`, `PREF_OPT_OUT`, `COLLAGE`, `TOPS`, `NP_LESS`, `NP_LESS_COVER`, `NP_MORE`) with `show_alert=True` ("This button belongs to another user."), keep `Action.WHOKNOWS` open to all group members, and eliminate double `query.answer()` calls; verify with unit tests in `tests/test_stability_security.py` asserting exact `query.answer` call counts and arguments.

## 4. HTML Safety, Media Transitions & Copy Alignment

- [x] 4.1 Fix `/set` and `/compare` no-arg usage replies (`&lt;username&gt;` / `<code>...</code>`), escape collage `ValueError` and exception error messages in `src/commands.py`, and add a shared `_update_or_replace_with_media` helper used by both `now_playing` and `status` that guards `if cover_url:` and handles text-to-photo transitions (sending a photo and deleting the old text message when `message.photo` is absent, or editing media/caption when present); verify with unit tests in `tests/test_stability_security.py`.
- [x] 4.2 Escape all dynamic user, Last.fm, URL, and changelog fields with `html.escape()` in `src/services.py` (`build_start_response`, `build_lastfm_username_set_response`, `build_np_response`, `build_status_response`, `build_tops_response`, `build_changelog_response`, `build_compare_response`, `build_collage_caption`, `GroupService`) and update `src/responses.py` (`start_response`, new `recent_tracks_empty`, accurate `/privacy` policy); verify with HTML-special-character unit tests in `tests/test_stability_security.py`.
- [x] 4.3 Unify mixed Catalan/English UI strings in `src/services.py` (`"👑 Who knows?"`, `"🔒 Hide me from group rankings"`, `"🔓 Show me in group rankings"`, `"Hidden from group rankings 🔒"`, `"Visible in group rankings 🔓"`, `"no text"`, `"filter ..."`, `"⚔️ NEW BAND KING!"`), update the affected assertion in `src/tests.py` (`test_collage_caption_with_style`), and verify with `tests/test_stability_security.py` and `src/tests.py`.

## 5. UX Fixes, Passive Group Discovery & Sentry Privacy

- [x] 5.1 Fix `/start` missing-username fallback (`first_name` or `"there"`, escaped) in `src/services.py`, fix `/status` empty recent tracks to return `recent_tracks_empty` instead of `user_not_found`, truncate `/crowns` user showcase cleanly before 4096 characters with `... and N more crowns`, delete the interactive `/collage` `"Generating..."` status message in `finally`, and update the interactive style-step confirm button label (`"✨ Skip & Generate"` / `"✅ Generate"`); verify with unit tests in `tests/test_stability_security.py`.
- [x] 5.2 Set `send_default_pii=False` in `sentry_sdk.init(...)` and register a low-priority passive group `MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, commands.track_group_member)` in `src/bot.py` with `track_group_member` in `src/commands.py` (ignoring bots and unlinked users, refreshing `ChatMember` for linked users); verify with unit tests in `tests/test_stability_security.py`.

## 6. Full Verification

- [x] 6.1 Run the full test suite (`python -m unittest src/tests.py tests/test_stability_security.py` or `pytest`) and verify all existing and new tests pass with zero failures and no unintended edits outside owned files.
