# telegram-bot-core Specification

## Purpose
Manages the core lifecycle, global defaults, startup command synchronization, and centralized error handling for the Telegram bot application.

## Requirements

### Requirement: Application Defaults Configuration
The Telegram bot application SHALL configure centralized defaults on startup, including HTML parse mode and disabled link previews by default for all outgoing messages.

#### Scenario: Sending messages without explicit formatting parameters
- **WHEN** any bot command or helper sends a message without specifying `parse_mode` or `link_preview_options`
- **THEN** Telegram automatically renders HTML formatting and disables link previews as configured in the application defaults

### Requirement: Automatic Bot Command Synchronization
The Telegram bot application SHALL automatically synchronize its registered command list and descriptions with the Telegram Bot API during initialization (`post_init`).

#### Scenario: Bot startup command registration
- **WHEN** the bot application finishes bootstrapping and begins listening for updates
- **THEN** the Telegram client command menu is updated with all available bot commands and their localized descriptions via `set_my_commands`

### Requirement: Centralized Global Error Handling
The Telegram bot application SHALL capture all uncaught exceptions occurring during update processing through a centralized error handler and initialize Sentry with `send_default_pii=False` so personal user data is not transmitted by default.

#### Scenario: Uncaught exception in command handler
- **WHEN** an unhandled exception or network error occurs while processing a command or callback
- **THEN** the error handler logs the exception traceback, forwards the error event to Sentry without default PII attached, and sends a user-friendly error notification to the affected chat if possible

### Requirement: Modern Dependency Alignment
The project SHALL declare and use `python-telegram-bot` version 22.8 or higher, ensuring compatibility with Telegram Bot API 9.x/10.0 and modern Python 3.14 features.

#### Scenario: Dependency verification
- **WHEN** dependencies are resolved and installed via the project package manager
- **THEN** `python-telegram-bot` resolves to version `==22.8` with all required asynchronous networking components

### Requirement: Accurate Privacy Policy and Account Deletion
The `/privacy` command SHALL accurately disclose all stored user data (`telegram_id`, `telegram_username`, `lastfm_username`, chat memberships, crowns, command logs) and document self-service removal via `/preferences` -> Unlink, which SHALL delete the user's record, cascaded memberships/crowns, and associated command logs.

#### Scenario: User inspects `/privacy`
- **WHEN** a user invokes `/privacy`
- **THEN** the response accurately lists stored data categories and instructs the user that `/preferences` -> Unlink deletes their data

#### Scenario: User unlinks their account
- **WHEN** a user confirms Unlink in `/preferences`
- **THEN** the database transaction deletes the `User` row (cascading `ChatMember` and `Crown`) and removes all `CommandLog` entries for that `telegram_user_id`

### Requirement: Durable and Indexed SQLite Persistence
The SQLite database layer SHALL configure `synchronous=1` (`NORMAL`) alongside WAL mode, preserve existing non-empty chat metadata during chat upserts, and maintain indexes on `CommandLog` (`timestamp`, `user_id`, `command`) including idempotent startup migrations for existing databases.

#### Scenario: Chat upsert called with empty metadata
- **WHEN** a database helper such as `upsert_crown` calls `get_or_create_chat(chat_id)` with empty `chat_name` and `chat_type` for an existing chat
- **THEN** the existing non-empty `telegram_chat_name` and `chat_type` remain intact and are not overwritten with empty strings

#### Scenario: Startup migrations run on an existing database
- **WHEN** `run_migrations()` executes against an existing SQLite database lacking `CommandLog` indexes
- **THEN** indexes on `commandlog(timestamp)`, `commandlog(user_id)`, and `commandlog(command)` are created idempotently without error
