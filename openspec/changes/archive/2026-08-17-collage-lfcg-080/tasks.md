# Tasks: collage-lfcg-080

## 1. Dependència

- [x] 1.1 A `pyproject.toml`, canviar `lastfmcollagegenerator>=0.6.0` a `>=0.8.0`
- [x] 1.2 Executar `uv sync` i verificar que `uv.lock` resol 0.8.0 sense conflictes
- [x] 1.3 Verificar import: `uv run python -c "from lastfmcollagegenerator.collage_generator import CollageGenerator; from lastfmcollagegenerator.presets import PRESET_NAMES; print(PRESET_NAMES)"`

## 2. Model d'opcions i parser (src/services.py)

- [x] 2.1 Crear dataclass `CollageOptions` amb tots els camps del design (entity, cols, rows, period, tile_size, theme, overlay_style, show_text, preset, corner_radius, border_width, border_color, spacing, fallback_style) i mètode `build_kwargs()` que retorni només claus no-per-defecte
- [x] 2.2 Refactoritzar `parse_collage_args` per retornar `CollageOptions` mantenint tota la sintaxi existent (mides, períodes, entitats, tile_size) sense canviar-ne el significat
- [x] 2.3 Afegir parsing de `theme:`, `overlay:` (àlies `ov:`/`style:`), `preset:` + àlies curts `story|post|header|wallpaper|4k`, flag `notext`, `corner:` (àlies `radius:`), `border:`, `border_color:` (àlies `bc:`), `spacing:` (àlies `gap:`), `fallback:`
- [x] 2.4 Validar valors enumerats contra constants de la llibreria 0.8.0 (`THEMES`, `OVERLAY_STYLES`, `FALLBACK_STYLES`, `PRESET_NAMES`) i límits numèrics (corner/border/spacing >= 0; border_color format hex o tupla vàlid), amb missatges d'error coherents amb els actuals
- [x] 2.5 Actualitzar el missatge d'ús ("Unrecognized parameter") amb la sintaxi nova

## 3. CollageService (src/services.py)

- [x] 3.1 Ampliar `generate_collage_image` amb els kwargs nous i passar-los a `self._generator.generate(...)` via `options.build_kwargs()`
- [x] 3.2 `CollageService.__init__` rep `cache_dir` opcional; per defecte `config.PROJECT_ROOT / "data" / "collage_cache"` amb `mkdir(parents=True, exist_ok=True)`
- [x] 3.3 Mantenir `asyncio.to_thread` i la conversió a `BytesIO`/PNG existent

## 4. Callback protocol (src/callbacks.py)

- [x] 4.1 Afegir camps opcionals a `Callback`: `theme: Optional[str]`, `overlay: Optional[str]`, `preset: Optional[str]`, `style: Optional[str]` (valors `"set"`/`"skip"`)
- [x] 4.2 `encode()`: parts noves com a parts 6-9, només si no buides; mantenir l'assert de 64 bytes
- [x] 4.3 `decode()`: lectura tolerant de les parts noves (len>5...8); callbacks antics de 5 parts segueixen vàlids
- [x] 4.4 Mapejos `to_collage_*` sense canvis; afegir helpers de codis curts de preset si cal (story→instagram-story, etc.)

## 5. Assistent interactiu (src/services.py + src/responses.py)

- [x] 5.1 Pas mida: afegir tercera fila amb presets socials (Story, Post, Header, Wallpaper, 4K) que codifiquen `preset=<codi>`
- [x] 5.2 Pas nou "Estil" quan hi ha entity+size+period i `style` buit: files de 5 temes i 5 overlays + botó "Skip"; botons d'estil codifiquen `style="set"` i el camp d'estil corresponent; Skip codifica `style="skip"`
- [x] 5.3 Noves plantilles de text a `responses.py` (pas d'estil, ús actualitzat) amb `Template` i `emojize`
- [x] 5.4 `build_collage_caption` accepta `theme/overlay_style/preset/show_text` opcionals i compon `$style_note`; verificar ús de `safe_substitute` per a la clau nova

## 6. Handlers (src/commands.py)

- [x] 6.1 `collage` (CLI): usar `CollageOptions` del parser i passar kwargs al service; caption amb opcions d'estil
- [x] 6.2 `_handle_collage`: derivar generació vs pas d'estil amb `cb.style`; presets generen amb `preset=` i mida del preset; passar estil al service i al caption
- [x] 6.3 Mantenir `COLLAGE_SEMAPHORE`, `send_chat_action` i gestió d'errors actuals

## 7. Tests (src/tests.py)

- [x] 7.1 Actualitzar `TestParseCollageArgs` al nou retorn (dataclass) i afegir casos per a cada arg nou + invàlids
- [x] 7.2 Actualitzar `TestCollageService` per verificar pas de kwargs nous a `generate()`
- [x] 7.3 Actualitzar/extendre `TestCallbackProtocol` amb roundtrip dels camps nous i decodificació de callbacks antics
- [x] 7.4 Actualitzar `TestViewServiceCollage`: captions amb estils, pas d'estil interactiu i fila de presets
- [x] 7.5 Executar `uv run python -m unittest discover -s src -p "test*.py"` i `uv run ruff check .` / `uv run ruff format . --check`

## 8. Documentació i tancament

- [x] 8.1 Afegir entrada a `CHANGELOG.md` documentant les noves opcions de `/collage`
- [x] 8.2 Revisar `CONTEXT.md` (taula de /collage i gotchas) si cal actualitzar
- [x] 8.3 Validar `openspec validate collage-lfcg-080 --strict`
