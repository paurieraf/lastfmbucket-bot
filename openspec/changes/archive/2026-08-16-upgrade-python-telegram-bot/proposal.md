## Why

Actualitzar la dependència `python-telegram-bot` des de la versió `22.5` a la darrera versió estable `22.8` (amb suport per a les darreres versions de la Telegram Bot API 9.x/10.0, millores de seguretat, tipat i rendiment) i aprofitar per revisar l'arquitectura de tots els comandaments del bot.

Aquesta revisió permetrà alinear el bot amb les millors pràctiques modernes de la llibreria:
- Centralitzar la configuració per defecte (`Defaults` per a `parse_mode=ParseMode.HTML` i `LinkPreviewOptions(is_disabled=True)`), evitant redundàncies a cada handler.
- Gestionar automàticament el registre de comandaments amb `set_my_commands` al cicle de vida (`post_init`), mantenint el menú d'autocompletat de Telegram sempre sincronitzat.
- Afegir un gestor d'errors global (`add_error_handler`) integrat amb Sentry i logs per capturar fallades inesperades i informar l'usuari amigablement.
- Revisar tots els comandaments (`/start`, `/np`, `/status`, `/tops`, `/collage`, `/preferences`, `/help`, `/changelog`, `/set`, `/privacy`, `/compare`, `/vibe`, `/roast`, `/recommend`) per aprofitar accessors idiomàtics (`update.effective_user`, `update.effective_chat`, `update.effective_message`), accions de xat asíncrones (`ChatAction.TYPING`, `ChatAction.UPLOAD_PHOTO`) i formatació resilient.

## What Changes

- **Actualització de dependències**: Actualitzar `python-telegram-bot==22.8` (i actualització de lockfile via `uv lock`) a `pyproject.toml`.
- **Configuració de l'Application i Cicle de Vida**:
  - Configurar `Defaults` amb `ParseMode.HTML` i `link_preview_options=LinkPreviewOptions(is_disabled=True)` a `ApplicationBuilder`.
  - Afegir ganxo `post_init` per registrar `set_my_commands` automàticament a l'inici del bot.
  - Afegir `add_error_handler` global per a gestió d'excepcions robusta.
- **Modernització de Comandaments i Callbacks**:
  - Refactoritzar el decorador `@log_command` per utilitzar `update.effective_user` i `update.effective_chat` de forma segura.
  - Revisar els comandaments d'IA (`/vibe`, `/roast`, `/recommend`) afegint feedback visual (`ChatAction.TYPING`) durant el processament i corregint el format Markdown/HTML.
  - Assegurar accions visuals de càrrega (`ChatAction.UPLOAD_PHOTO`) a `/collage` i neteja de missatges temporals.
  - Optimitzar els handlers de missatges (`reply_text`, `edit_text`, `reply_photo`) aprofitant els valors per defecte de l'`Application`.
- **Verificació i Cobertura de Tests**:
  - Actualitzar i ampliar la suite de proves unitàries a `src/tests.py` per validar comandaments, callbacks i comportaments asíncrons.

## Capabilities

### New Capabilities
- `telegram-bot-core`: Inicialització d'`Application` amb `Defaults`, gestió de cicle de vida (`post_init`), `set_my_commands` automàtic, gestió centralitzada d'errors i actualització a `python-telegram-bot==22.8`.
- `bot-command-handlers`: Estandardització i modernització de tots els comandaments i callbacks del bot utilitzant accessors nadius de PTB (`effective_user`, `effective_chat`), accions de xat (`ChatAction`), decoradors segurs i formats HTML/Markdown protegits.

### Modified Capabilities
<!-- No existing capability specs in openspec/specs/ yet -->

## Impact

- **Fitxers modificats**: `pyproject.toml`, `uv.lock`, `src/bot.py`, `src/commands.py`, `src/callbacks.py`, `src/services.py`, `src/tests.py`.
- **Dependències**: `python-telegram-bot` actualitzat de `22.5` a `22.8`.
- **APIs / Interfície**: El menú de comandaments de Telegram s'autocompletarà i sincronitzarà automàticament per als usuaris; l'experiència d'usuari millorarà amb millor gestió d'errors i indicadors d'estat (typing/uploading).
