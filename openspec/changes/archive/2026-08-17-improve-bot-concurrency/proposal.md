# Proposal: Improve Bot Concurrency

## Why

The bot processes Telegram updates strictly one by one (`concurrent_updates=False` by default in python-telegram-bot) and synchronous pylast/SQLite I/O blocks the asyncio event loop. With ~20 users, a single slow `/roast` (Ollama generation, 30-60s) freezes every other command for every user; `/collage` also feels slow. Updates should be processed in parallel and blocking I/O must not stall the loop.

## What Changes

- Enable concurrent update processing in the PTB `Application` (`concurrent_updates(True)`).
- Offload blocking Last.fm (pylast) calls to worker threads via `asyncio.to_thread`, so the event loop stays responsive.
- Bound concurrent Last.fm API requests with a semaphore to respect Last.fm rate limits.
- Check Ollama model availability once at startup (`post_init`) instead of on every AI command.
- Parallelize independent Last.fm fetches inside `/compare` and `/roast` with `asyncio.gather`.
- Observable command outputs remain unchanged; only latency and responsiveness improve.

## Capabilities

### New Capabilities

- `bot-concurrency`: parallel update processing, non-blocking Last.fm access, bounded API concurrency, and startup-time AI model readiness.

### Modified Capabilities

None. Existing spec-level behaviors (`telegram-bot-core`, `bot-command-handlers`, `collage-generation`) keep the same observable outputs.

## Impact

- `src/bot.py`: `ApplicationBuilder` concurrency setting, model readiness in `post_init`.
- `src/services.py`: `LastfmService` methods become async (to_thread + semaphore); `ViewService` awaits them.
- `src/commands.py`: handlers awaiting the new async service methods; `gather` for `/compare` and `/roast`.
- `src/ai.py`: model check moved to startup with lazy retry.
- `src/db.py`: add `busy_timeout` pragma; verify single-thread usage assumption holds.
- No new runtime dependencies (stdlib `asyncio` only).
- Risks: Last.fm rate limiting (mitigated by semaphore), pylast thread-safety (verified by spike task, fallback documented), Ollama request queueing under concurrent AI commands.
