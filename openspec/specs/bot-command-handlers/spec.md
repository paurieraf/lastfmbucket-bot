# bot-command-handlers Specification

## Purpose
Defines the behavior, context extraction, visual feedback indicators, and resilient message formatting for all user-facing bot commands and interactive callbacks.

## Requirements

### Requirement: Robust Context and User Extraction
Command and callback handlers, including logging decorators, SHALL extract user and chat metadata using resilient context properties (`effective_user`, `effective_chat`, `effective_message`) without failing on callback queries or channel updates.

#### Scenario: User issues command from group chat or callback button
- **WHEN** a user triggers a command in a group or presses an inline keyboard button
- **THEN** the logging decorator and command logic resolve the user ID, username, and chat details safely without raising attribute errors

### Requirement: Interactive Progress and Chat Actions
Long-running commands such as collage generation and AI operations (`/vibe`, `/roast`, `/recommend`, `/collage`) SHALL display immediate visual feedback to the user using Telegram chat actions (`ChatAction.TYPING` or `ChatAction.UPLOAD_PHOTO`).

#### Scenario: User requests AI vibe or roast
- **WHEN** a user sends `/vibe`, `/roast`, or `/recommend`
- **THEN** the bot immediately signals `typing` status in the chat while awaiting the AI model generation response

#### Scenario: User generates collage
- **WHEN** a user submits collage parameters or confirms inline selections
- **THEN** the bot signals `upload_photo` action in the chat while generating and compositing artwork tiles

### Requirement: Resilient Formatting and Escape Handling
All bot command responses, usage prompts, error messages, changelogs, and Last.fm-derived outputs SHALL escape dynamic text for HTML (`ParseMode.HTML`) to prevent Telegram `BadRequest` entity parse errors and HTML injection.

#### Scenario: AI generates response containing special characters
- **WHEN** an AI recommendation, roast, or vibe text contains characters like underscores, asterisks, or brackets
- **THEN** the message is rendered safely to the user without causing Telegram `BadRequest` entity parse errors

#### Scenario: Command invoked without required arguments
- **WHEN** a user sends `/set` or `/compare` without arguments
- **THEN** the usage prompt escapes angle brackets (or wraps placeholders in `<code>` tags) so Telegram renders the message without raising `BadRequest`

#### Scenario: Dynamic metadata or error text contains HTML special characters
- **WHEN** a Telegram username, Last.fm username, artist, album, track title, URL, changelog file, or collage error message contains `<`, `>`, `&`, or quotes
- **THEN** all dynamic fields are HTML-escaped before substitution into templates or `<pre>` blocks and render safely without parse errors

### Requirement: Interactive Button Callbacks
Interactive inline buttons SHALL encode payloads within Telegram's 64-byte limit using compact short codes (raising `ValueError` on overflow while decoding legacy payloads), validate `from_user.id == owner_id` for user-scoped actions, acknowledge each callback query once, and handle text-to-photo media transitions safely.

#### Scenario: User clicks pagination or entity selection button
- **WHEN** a user taps an inline button on `/tops` or `/collage`
- **THEN** the callback query is acknowledged, and the view updates to the selected page, period, or entity view without creating duplicate message threads

#### Scenario: Another user clicks a user-scoped button in a group chat
- **WHEN** a user whose Telegram ID differs from `owner_id` taps a button for `PREF_UNLINK`, `PREF_OPT_OUT`, `COLLAGE`, `TOPS`, `NP_LESS`, `NP_LESS_COVER`, or `NP_MORE`
- **THEN** the bot answers the callback query once with `show_alert=True` ("This button belongs to another user.") and aborts without modifying the message or account state

#### Scenario: Group member clicks the WhoKnows button on another user's `/np`
- **WHEN** any group member taps the `Action.WHOKNOWS` button on a `/np` message
- **THEN** the bot permits the action, answers the callback query once (with `show_alert=True` only if no track is found), and posts the artist ranking

#### Scenario: User reveals album cover from a text-only `/np` or `/status` message
- **WHEN** a user clicks the cover button on a text-only message and a cover URL is available
- **THEN** the bot sends a new photo message with the caption and keyboard and deletes the previous text message instead of failing on `edit_message_media`

#### Scenario: User clicks cover button when no cover artwork exists
- **WHEN** a user triggers `show_cover=True` on `/np` or `/status` and `cover_url` is `None`
- **THEN** the bot updates the existing text or caption in place without calling `edit_media` with `None`

#### Scenario: Encoding callback data for 64-bit Telegram user IDs
- **WHEN** a collage callback with 64-bit `owner_id`, entity, period, size, theme, overlay, preset, and style is encoded
- **THEN** the encoded UTF-8 payload stays within 64 bytes using compact short codes, round-trips losslessly, and `decode()` still accepts legacy full-string payloads

### Requirement: Validated Last.fm User Lookup
Linking a Last.fm account via `/set` SHALL verify that the username actually exists on Last.fm through a real API request rather than instantiating an unvalidated client object.

#### Scenario: User links a nonexistent Last.fm username
- **WHEN** a user runs `/set nonexistent_user_xyz` and Last.fm returns a `WSError` (user not found)
- **THEN** the bot does not save the username and responds with a user-not-found message

#### Scenario: User links a valid Last.fm username
- **WHEN** a user runs `/set valid_user` and the Last.fm API lookup succeeds
- **THEN** the bot persists the mapping and confirms the linked username

### Requirement: Graceful Edge-Case Command Handling
User-facing commands SHALL handle missing Telegram usernames and empty Last.fm listening histories gracefully without confusing placeholders or false unlinked errors.

#### Scenario: User without a Telegram username runs `/start`
- **WHEN** a user whose `telegram_user.username` is `None` invokes `/start`
- **THEN** the bot greets them using their HTML-escaped `first_name` (or `"there"` if unavailable) instead of `Hi @None`

#### Scenario: Linked user with zero recent tracks runs `/status`
- **WHEN** a user with a linked Last.fm account has an empty recent-tracks history
- **THEN** the bot displays a "No recent tracks found" message rather than claiming no Last.fm account is set

### Requirement: Consistent English UI Copy
User-facing button labels, status banners, and captions SHALL use consistent English copy across all commands and inline keyboards.

#### Scenario: User opens `/preferences`, `/np`, `/whoknows`, or `/collage`
- **WHEN** the bot renders inline buttons, opt-out feedback, dethronement banners, or collage captions
- **THEN** all labels and status phrases are rendered in English without mixed Catalan strings
