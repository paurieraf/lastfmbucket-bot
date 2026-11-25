# bot-concurrency Specification

## Purpose
Ensures the bot processes Telegram updates in parallel, keeps its event loop responsive under blocking Last.fm I/O, bounds API concurrency, and prepares AI capabilities at startup.

## Requirements

### Requirement: Concurrent update processing
The bot application SHALL process multiple incoming Telegram updates concurrently, so a slow command for one user does not block commands from other users.

#### Scenario: Slow command does not block another user
- **WHEN** user A issues a slow AI command (e.g. `/roast`) and user B issues a fast command (e.g. `/np`) while A's command is still executing
- **THEN** user B's command starts and completes without waiting for user A's command to finish

#### Scenario: Multiple simultaneous commands
- **WHEN** several users issue commands at the same time
- **THEN** each command is handled independently and all receive their responses

### Requirement: Non-blocking Last.fm access
All Last.fm API network calls triggered by command handling—including track album resolution and album cover image lookups—SHALL execute off the asyncio event loop within the configured Last.fm concurrency bound, so network latency does not stall update processing for other users.

#### Scenario: Event loop stays responsive during API calls
- **WHEN** a command triggers one or more Last.fm HTTP requests that take seconds to respond
- **THEN** other queued updates continue to be processed while those requests are in flight

#### Scenario: Now-playing and status album/cover lookups do not block the event loop
- **WHEN** a user invokes `/np` or `/status` (with or without cover art enabled)
- **THEN** track album lookup and album cover URL lookup execute off the event loop under the Last.fm concurrency limit

### Requirement: Bounded Last.fm API concurrency
The bot SHALL cap the number of simultaneous Last.fm API requests to a configurable limit, protecting the shared API key from rate-limit errors under concurrent load.

#### Scenario: Burst of commands stays within the limit
- **WHEN** more concurrent Last.fm requests would be needed than the configured cap (default 8)
- **THEN** excess requests wait until a slot frees, and the cap is never exceeded

#### Scenario: Cap is configurable
- **WHEN** the operator sets the `LASTFM_MAX_CONCURRENT` environment variable
- **THEN** the bot uses that value as the concurrency cap instead of the default

### Requirement: Startup-time AI model readiness
The bot SHALL verify Ollama model availability once during application startup, and AI commands SHALL NOT perform per-invocation model-list checks.

#### Scenario: AI command without redundant checks
- **WHEN** a user invokes `/vibe`, `/roast`, or `/recommend` after startup
- **THEN** the command performs its generation request without first listing models on Ollama

#### Scenario: Model unavailable at startup
- **WHEN** the model cannot be verified or pulled during startup
- **THEN** AI commands return the existing friendly unavailable message and may retry readiness lazily

### Requirement: Parallel independent fetches within a command
Commands that require multiple independent Last.fm datasets SHALL fetch them concurrently and avoid redundant API calls, producing output identical to the previous format.

#### Scenario: Compare fetches both users concurrently
- **WHEN** a user runs `/compare <other_user>`
- **THEN** the bot performs at most four Last.fm API calls in parallel (each user's playcount and top-50 overall artists), derives both users' top-3 artists and common artists in memory, and returns the response content matching the previous format

#### Scenario: Roast fetches top artists and tracks concurrently
- **WHEN** a user runs `/roast`
- **THEN** top artists and top tracks are requested in parallel and the generated roast is unaffected in format

### Requirement: Non-blocking local I/O during update handling
Synchronous local I/O triggered by incoming Telegram updates—including database writes for command logging and passive chat-member tracking, and reading the changelog file—SHALL execute off the asyncio event loop so disk or SQLite lock contention cannot stall concurrent updates.

#### Scenario: Command logging and passive member tracking do not stall the event loop
- **WHEN** a user sends a command or a message in a tracked chat while SQLite is busy
- **THEN** the database write runs off the event loop and other concurrent updates continue processing

#### Scenario: Changelog file read does not block the event loop
- **WHEN** a user invokes `/changelog`
- **THEN** reading the changelog file from disk executes off the event loop and returns the formatted changelog or fallback message

### Requirement: Bounded and resilient AI generation
AI text generation requests SHALL read connection, model, timeout, and concurrency settings from centralized configuration, enforce an explicit request timeout, bound concurrent generations to a configurable limit (default 1), and recover automatically after Ollama restarts.

#### Scenario: Concurrent AI requests are serialized within the configured bound
- **WHEN** multiple users invoke AI commands (`/vibe`, `/roast`, `/recommend`) simultaneously with the default concurrency limit of 1
- **THEN** at most one generation request runs against Ollama at a time while additional requests wait for a slot

#### Scenario: Hung Ollama request times out cleanly
- **WHEN** an Ollama generation request exceeds the configured timeout
- **THEN** the request is aborted, the user receives the command's friendly fallback message, and the bot remains responsive

#### Scenario: Automatic recovery after Ollama restart
- **WHEN** an AI generation fails due to a connection, runtime, or timeout error after startup succeeded
- **THEN** the bot marks the model as not ready so a subsequent request after the cooldown period re-verifies or pulls the model and recovers without restarting the bot
