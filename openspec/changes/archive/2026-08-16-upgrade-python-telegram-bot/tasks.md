## 1. Actualització de Dependències i Entorn

- [x] 1.1 Actualitzar `python-telegram-bot==22.8` a `pyproject.toml`
- [x] 1.2 Executar `uv sync` / `uv lock` per actualitzar el lockfile i instal·lar la versió 22.8 al venv

## 2. Inicialització d'Application i Cicle de Vida

- [x] 2.1 Configurar `Defaults` amb `ParseMode.HTML` i `link_preview_options=LinkPreviewOptions(is_disabled=True)` a `ApplicationBuilder` a `src/bot.py`
- [x] 2.2 Definir la llista de comandaments `BOT_COMMANDS` i implementar el ganxo asíncron `post_init` per registrar `set_my_commands`
- [x] 2.3 Implementar i registrar el gestor d'errors global (`error_handler`) amb registre a logs i captura d'excepcions a Sentry

## 3. Modernització de Comandaments i Decoradors

- [x] 3.1 Refactoritzar el decorador `@log_command` a `src/commands.py` per utilitzar de forma resilient `update.effective_user` i `update.effective_chat`
- [x] 3.2 Revisar i simplificar handlers estàndard (`/start`, `/np`, `/status`, `/tops`, `/preferences`, `/help`, `/changelog`, `/set`, `/privacy`, `/compare`) aprofitant els valors per defecte de l'Application i accessors `effective_*`
- [x] 3.3 Millorar els comandaments d'IA (`/vibe`, `/roast`, `/recommend`) afegint `ChatAction.TYPING` asíncron i formatació HTML segura en lloc de Markdown propens a errors
- [x] 3.4 Optimitzar el comandament `/collage` amb `ChatAction.UPLOAD_PHOTO` i gestió neta d'estats visuals temporals
- [x] 3.5 Verificar i polir el flux de callbacks a `src/callbacks.py` i `button_handler`

## 4. Proves i Validació

- [x] 4.1 Actualitzar i ampliar els tests unitaris a `src/tests.py` cobrint decoradors, cicle de vida, gestor d'errors i comandaments
- [x] 4.2 Executar `uv run python src/tests.py` i verificar que totes les proves passen
- [x] 4.3 Executar `uv run ruff check src/` i verificar conformitat d'estil i format
