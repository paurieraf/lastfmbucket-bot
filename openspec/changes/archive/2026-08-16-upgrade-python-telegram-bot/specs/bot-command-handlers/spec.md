## Purpose

Defines the behavior, context extraction, visual feedback indicators, and resilient message formatting for all user-facing bot commands and interactive callbacks.

## ADDED Requirements

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
All bot command responses and AI-generated outputs SHALL use safe message formatting (HTML or sanitized Markdown) to prevent Telegram parsing exceptions.

#### Scenario: AI generates response containing special characters
- **WHEN** an AI recommendation, roast, or vibe text contains characters like underscores, asterisks, or brackets
- **THEN** the message is rendered safely to the user without causing Telegram `BadRequest` entity parse errors

### Requirement: Interactive Button Callbacks
Interactive inline buttons SHALL decode callback data securely, validate ownership against the initiating user when applicable, acknowledge the callback immediately via `answer()`, and edit or replace the current message seamlessly.

#### Scenario: User clicks pagination or entity selection button
- **WHEN** a user taps an inline button on `/tops` or `/collage`
- **THEN** the callback query is acknowledged, and the view updates to the selected page, period, or entity view without creating duplicate message threads
