# Tasks: Implement Group WhoKnows & Crowns System

- [x] 1. Database Schema & Persistence Layer (`src/db.py`)
  - [x] 1.1 Add `ChatMember` model with `chat`, `user`, `last_active`, `opt_out`, and composite unique index.
  - [x] 1.2 Add `Crown` model with `chat`, `artist_name`, `artist_url`, `user`, `playcount`, `updated_at`, and composite unique index.
  - [x] 1.3 Implement `track_chat_member(chat_id, user_id)` helper.
  - [x] 1.4 Implement `get_linked_chat_members(chat_id)` querying non-opt-out users with valid `lastfm_username`.
  - [x] 1.5 Implement `get_crown(chat_id, artist_name)`, `upsert_crown(chat_id, artist_name, artist_url, user, playcount)`, and `get_chat_crowns_leaderboard(chat_id)`.
  - [x] 1.6 Implement `get_user_crowns(chat_id, user_id)` and `toggle_user_group_opt_out(user_id)`.
  - [x] 1.7 Ensure `MODELS` list includes `ChatMember` and `Crown` for automatic table creation.

- [x] 2. Last.fm Client Extensions (`src/lastfm.py`)
  - [x] 2.1 Add `get_artist_canonical_info(artist_name)` to resolve official name and Last.fm URL.
  - [x] 2.2 Add `get_user_artist_playcount(username, artist_name)` to query playcount for a user.

- [x] 3. Response Templates (`src/responses.py`)
  - [x] 3.1 Add HTML template for `/whoknows` ranking with Last.fm link, podium badges, scrobbles, and dethronement banner.
  - [x] 3.2 Add HTML template for `/crowns` group leaderboard (Hall of Fame).
  - [x] 3.3 Add HTML template for `/crowns @user` (individual crowns showcase).

- [x] 4. Group & Crown Service Layer (`src/services.py`)
  - [x] 4.1 Implement `GroupService` class handling `/whoknows` ranking logic with concurrent `asyncio.gather` playcount lookups.
  - [x] 4.2 Add dethronement detection comparing previous `Crown` holder with new #1.
  - [x] 4.3 Implement `GroupService.get_crowns_leaderboard` and `GroupService.get_user_crowns`.
  - [x] 4.4 Update `ViewService` / `bot_data` to instantiate and expose `GroupService`.

- [x] 5. Command Handlers & Telegram UX (`src/commands.py`, `src/callbacks.py`)
  - [x] 5.1 Add `/whoknows` (and `/wk`) command handler resolving artist from args, reply, or caller's `/np`.
  - [x] 5.2 Add `/crowns` (and `/mycrowns`) command handler.
  - [x] 5.3 Add `Action.WHOKNOWS` callback action and attach `👑 Qui ho coneix?` button to Now Playing card.
  - [x] 5.4 Add group privacy toggle button in `/preferences` and handle callback.
  - [x] 5.5 Update `BOT_COMMANDS` list with `/whoknows` and `/crowns`.
  - [x] 5.6 Ensure `@log_command` / message handlers call `db.track_chat_member`.

- [x] 6. Quality Assurance & Documentation
  - [x] 6.1 Add unit and integration tests in `src/tests.py` for all new models, service methods, and commands.
  - [x] 6.2 Run `pytest` and verify all tests pass.
  - [x] 6.3 Update `README.md`, `ARCHITECTURE.md`, `CONTEXT.md`, `PROJECT.md`, `CHANGELOG.md`, and `docs/PRODUCT_PRESENTATION.md`.

