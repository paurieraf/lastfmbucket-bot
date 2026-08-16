## Purpose

Ensures the bot processes Telegram updates in parallel, keeps its event loop responsive under blocking Last.fm I/O, bounds API concurrency, and prepares AI capabilities at startup.

## ADDED Requirements

### Requirement: Concurrent update processing
The bot application SHALL process multiple incoming Telegram updates concurrently, so a slow command for one user does not block commands from other users.

#### Scenario: Slow command does not block another user
- **WHEN** user A issues a slow AI command (e.g. `/roast`) and user B issues a fast command (e.g. `/np`) while A's command is still executing
- **THEN** user B's command starts and completes without waiting for user A's command to finish

#### Scenario: Multiple simultaneous commands
- **WHEN** several users issue commands at the same time
- **THEN** each command is handled independently and all receive their responses

### Requirement: Non-blocking Last.fm access
All Last.fm API network calls triggered by command handling SHALL execute off the asyncio event loop, so network latency does not stall update processing for other users.

#### Scenario: Event loop stays responsive during API calls
- **WHEN** a command triggers one or more Last.fm HTTP requests that take seconds to respond
- **THEN** other queued updates continue to be processed while those requests are in flight

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
Commands that require multiple independent Last.fm datasets SHALL fetch them concurrently, producing output identical to the previous sequential behavior.

#### Scenario: Compare fetches both users concurrently
- **WHEN** a user runs `/compare <other_user>`
- **THEN** stats for both users are requested in parallel and the response content matches the previous format

#### Scenario: Roast fetches top artists and tracks concurrently
- **WHEN** a user runs `/roast`
- **THEN** top artists and top tracks are requested in parallel and the generated roast is unaffected in format
