## Context

El projecte `lastfmbucket-bot` és un bot de Telegram asíncron desenvolupat en Python 3.14 amb la llibreria `python-telegram-bot` (actualment fixada a la versió `22.5`).

L'estructura actual del bot:
- `src/bot.py` inicialitza l'`Application` bàsica sense valors per defecte (`Defaults`), sense ganxos de cicle de vida (`post_init` / `post_shutdown`) i sense un gestor d'errors registrat a l'aplicació (`add_error_handler`).
- Els comandaments a `src/commands.py` configuren individualment i de manera repetitiva paràmetres com `parse_mode=telegram.constants.ParseMode.HTML` i `link_preview_options=LinkPreviewOptions(is_disabled=True)`.
- El decorador `@log_command` accedeix directament a `update.message.from_user` en lloc d'utilitzar les propietats més resilients de PTB com `update.effective_user` i `update.effective_chat`.
- Els comandaments generatius d'IA (`/vibe`, `/roast`, `/recommend`) utilitzen `parse_mode="Markdown"` que pot fallar en cas de caràcters especials en títols o artistes, i no emeten accions visuals de `ChatAction.TYPING` mentre esperen el model d'IA.

## Goals / Non-Goals

**Goals:**
- Actualitzar `python-telegram-bot` a la versió `22.8` a `pyproject.toml` i sincronitzar `uv.lock`.
- Centralitzar els valors per defecte mitjançant `Defaults(parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))` a `ApplicationBuilder`.
- Implementar el cicle de vida `post_init` per registrar automàticament els comandaments amb `await application.bot.set_my_commands(...)` i sincronitzar el menú d'autocompletat de Telegram.
- Implementar un gestor d'errors global (`add_error_handler`) que registri traces, enviï l'excepció a Sentry i respongui a l'usuari amb un missatge d'error amigable.
- Uniformitzar tots els comandaments i decoradors amb els accessors recomanats de PTB (`effective_user`, `effective_chat`, `effective_message`).
- Integrar accions de xat (`ChatAction.TYPING` i `ChatAction.UPLOAD_PHOTO`) en processos asíncrons llargs (`/vibe`, `/roast`, `/recommend`, `/collage`).
- Convertir la sortida d'IA a HTML segur o Markdown sanititzat per evitar errors `BadRequest: Can't parse entities`.
- Mantenir la suite de proves unitàries amb 100% de verificació verda.

**Non-Goals:**
- Modificar el model de dades Peewee a `src/db.py`.
- Reescriptura del panell web d'administració NiceGUI a `src/admin.py`.
- Canviar el client Last.fm (`pylast`) o el proveïdor de models d'IA (`ollama`).

## Decisions

### Decisió 1: Centralització de configuració amb `Defaults`
Configurarem `Defaults` a l'`ApplicationBuilder`:
```python
defaults = Defaults(
    parse_mode=telegram.constants.ParseMode.HTML,
    link_preview_options=LinkPreviewOptions(is_disabled=True),
)
app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).defaults(defaults).build()
```
*Raonament*: Elimina la duplicació de codi a desenes de funcions de `commands.py` i garanteix que qualsevol nou comandament tingui deshabilitades les previsualitzacions d'enllaços i utilitzi HTML de manera consistent.
*Alternatives considerades*: Mantenir paràmetres explícits a cada crida (més verbós i propens a oblits).

### Decisió 2: Sincronització automàtica de comandaments a `post_init`
Definirem una llista estructurada de comandaments `BotCommand` i l'aplicarem via `post_init`:
```python
BOT_COMMANDS = [
    BotCommand("np", "Currently playing track"),
    BotCommand("status", "Recent tracks"),
    BotCommand("tops", "Top artists, albums, or tracks"),
    BotCommand("collage", "Generate visual album/artist collage"),
    BotCommand("set", "Link your Last.fm username"),
    BotCommand("compare", "Compare listening stats with another user"),
    BotCommand("vibe", "AI analysis of your current vibe"),
    BotCommand("roast", "AI roast of your music taste"),
    BotCommand("recommend", "AI-powered music recommendations"),
    BotCommand("preferences", "Manage bot preferences"),
    BotCommand("help", "Help and command list"),
    BotCommand("changelog", "Recent bot updates"),
    BotCommand("privacy", "Privacy policy"),
]

async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(BOT_COMMANDS)
```
*Raonament*: Evita haver de configurar manualment els comandaments a @BotFather cada vegada que s'afegeix o canvia un comandament, assegurant que els usuaris sempre vegin la llista actualitzada.

### Decisió 3: Gestor d'errors global (`add_error_handler`)
Implementarem una funció `error_handler(update: object, context: ContextTypes.DEFAULT_TYPE)`:
```python
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    if config.SENTRY_DSN:
        sentry_sdk.capture_exception(context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ An unexpected error occurred while processing your request.",
            )
        except Exception:
            pass
```
*Raonament*: PTB v22 aïlla els errors dels handlers; sense `add_error_handler`, les fallades no controlades només s'imprimeixen als logs per defecte sense notificar l'usuari ni integrar-se formalment amb la telemetria de l'aplicació.

### Decisió 4: Formatació HTML segura per a respostes d'IA
Substituirem `parse_mode="Markdown"` als comandaments `/vibe`, `/roast` i `/recommend` per text estructurat en HTML (`<b>...</b>`) o text pla amb capçaleres netes.
*Raonament*: El mode Markdown clàssic de Telegram llança excepcions `BadRequest` si la resposta de l'IA conté caràcters reservats com `_` o `*` que no estiguin tancats o escapats. HTML és més robust i coherent amb la resta de l'aplicació.

### Decisió 5: Resiliència en decoradors i accessors
El decorador `@log_command` i els handlers utilitzaran `update.effective_user`, `update.effective_chat` i `update.effective_message`:
*Raonament*: Garanteix un funcionament uniforme tant si l'actualització arriba per missatge directe, xat de grup o callback d'un botó en línia.

## Risks / Trade-offs

- **[Risc] Sobreescriptura inadvertida del format de text** → *Mitigació*: Revisar totes les crides de resposta; per a missatges que necessitin text pla estricte (com la descripció del bot a `/help`), passar `parse_mode=None` explícitament.
- **[Risc] Caràcters especials en títols de Last.fm que puguin trencar HTML** → *Mitigació*: Assegurar que `html.escape` s'utilitza a `ViewService` per a noms d'artistes, títols de cançons i usuaris.
- **[Risc] Límits de velocitat de l'API de Telegram** → *Mitigació*: `set_my_commands` s'executa una sola vegada durant el `post_init`. Les accions de xat (`send_chat_action`) s'encapsulen en blocs `try/except` per evitar que un error no crític de xat bloquegi l'execució.
