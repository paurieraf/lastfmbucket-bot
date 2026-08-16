## 1. Service Layer & Collage Generation

- [x] 1.1 Implement CollageService in `src/services.py` with asynchronous generation bridge (`asyncio.to_thread`) and PIL to BytesIO buffer conversion
- [x] 1.2 Add helper and parser for collage arguments (dimensions, periods, entities)

## 2. Telegram Bot Callbacks & Interactive UI

- [x] 2.1 Update `src/callbacks.py` with `Action.COLLAGE` and compact serialization for collage options (size, entity, period)
- [x] 2.2 Implement inline keyboard builder for interactive collage selection in `src/services.py`

## 3. Bot Handlers & Registration

- [x] 3.1 Implement `/collage` command handler and callback handler in `src/commands.py`
- [x] 3.2 Add collage response templates and error messages in `src/responses.py`
- [x] 3.3 Register `COLLAGE_COMMAND` handler in `src/bot.py` and initialize `CollageService` in bot_data
- [x] 3.4 Update `/help` command output and README to document `/collage`

## 4. Verification & Testing

- [x] 4.1 Write automated unit tests for argument parsing, CollageService, and callback decoding
- [x] 4.2 Validate end-to-end bot startup and syntax validation with Ruff
