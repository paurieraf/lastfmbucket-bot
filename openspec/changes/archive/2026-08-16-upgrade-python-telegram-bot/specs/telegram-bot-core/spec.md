## Purpose

Manages the core lifecycle, global defaults, startup command synchronization, and centralized error handling for the Telegram bot application.

## ADDED Requirements

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
The Telegram bot application SHALL capture all uncaught exceptions occurring during update processing through a centralized error handler.

#### Scenario: Uncaught exception in command handler
- **WHEN** an unhandled exception or network error occurs while processing a command or callback
- **THEN** the error handler logs the exception traceback, forwards the error event to Sentry, and sends a user-friendly error notification to the affected chat if possible

### Requirement: Modern Dependency Alignment
The project SHALL declare and use `python-telegram-bot` version 22.8 or higher, ensuring compatibility with Telegram Bot API 9.x/10.0 and modern Python 3.14 features.

#### Scenario: Dependency verification
- **WHEN** dependencies are resolved and installed via the project package manager
- **THEN** `python-telegram-bot` resolves to version `==22.8` with all required asynchronous networking components
