# Design: collage-lfcg-080

## Context

Motivació: vegeu proposal.md.

Estat actual (0.6.0):
- `CollageService` (src/services.py) crea `CollageGenerator` i passa només `entity`, `username`, `cols`, `rows`, `period`, `tile_size`.
- `parse_collage_args` retorna una tupla `(entity, cols, rows, period, tile_size)` i llegeix límits de constants de la classe (`MAX_COLS`, etc.).
- `Callback` (src/callbacks.py) codifica `"1|cl|<owner>|<entity>|<period>|<size>"` amb límit de 64 bytes.
- Flux interactiu: entitat → mida (2 files de 3) → període (2 files de 3) → generació.
- `docker-compose.yml` munta `./data:/app/data` al contenidor del bot.

API 0.8.0 (verificada contra el wheel publicat): `generate()` afegeix `theme`, `overlay_style`, `show_text`, `font_path`, `preset`, `cache_dir`, `cache_ttl_override`, `rate_limit`, `fallback_style`, `corner_radius`, `border_width`, `border_color`, `spacing`. Els pins `Requires-Dist` són idèntics als de 0.6.0 → actualitzar no trenca resolució. Nous mòduls interns: `theme`, `presets`, `cache` (SQLite a `~/.cache/lastfm-collage/`), `network` (rate limit 5.0 req/s per defecte), `fallback_art`.

## Goals / Non-Goals

**Goals:**
- Exposar totes les opcions 0.8.0 útils per a Telegram via CLI args i assistent interactiu.
- Cache d'artwork persistent dins del volum `./data` (sense canvis de docker-compose).
- Compatibilitat total: callbacks antics (sense camps nous) segueixen decodificant; args CLI existents no canvien de significat.

**Non-Goals:**
- `font_path` (requereix fitxers .ttf/.otf al contenidor; sense font custom no hi ha valor afegit).
- `cache_ttl_override` i `rate_limit` exposats al CLI/interactiu: s'usen amb valors per defecte de la llibreria (decisions d'infra, no de UX). Es mantenen com a kwargs del service per si calgués.
- Persistir estil preferit per usuari (cap camp nou a la DB).

## Decisions

1. **Dataclass `CollageOptions` en lloc de la tupla** de `parse_collage_args`.
   - Motiu: 14 opcions no caben en una tupla llegible; les crides actuals i els tests es refactoritzaran igualment.
   - Camps: `entity, cols, rows, period, tile_size, theme, overlay_style, show_text, preset, corner_radius, border_width, border_color, spacing, fallback_style`.
   - Mètode `build_kwargs() -> dict` que només inclou claus amb valors no-per-defecte (perquè la llibreria mantingui els seus defaults).
   - Alternativa descartada: dict pla retornat pel parser — pitjor tipat.

2. **Sintaxi CLI per als nous args** (estil `key:value`, coherent amb `tile_size:300` actual):
   - `theme:neon` (àlies: `tema:`), `overlay:pill` (àlies: `ov:`, `style:`), `preset:instagram-story` + àlies curts `story|post|header|wallpaper|4k` (prefixats `preset:` o directes).
   - Flags: `notext` (show_text=False).
   - Geomètrics: `corner:12` (àlies `radius:`), `border:3`, `border_color:#FF5A5F` (àlies `bc:`), `spacing:8` (àlies `gap:`).
   - `fallback:gradient|black`.
   - Validació a `parse_collage_args` amb els mateixos missatges d'error que ara (límits numèrics, valors enumerats provinents de constants 0.8.0 importables: `THEMES`, `OVERLAY_STYLES`, `FALLBACK_STYLES`, `PRESET_NAMES` de `lastfmcollagegenerator.presets` — evitar hardcodar llistes).
   - Alternativa descartada: arguments posicionals nous — massa ambigus amb mides/períodes.

3. **Callback protocol extens** sense trencar els antics:
   - Parts noves opcionals 6,7,8: `theme`, `overlay`, `preset` (codis compactes: `d|dm|l|g|s|n`… no — es fan servir els strings curts de la llibreria directament, p. ex. `neon`, `pill`, `story`).
   - `encode()` només afegeix parts no buides; `decode()` llegeix len>5/6/7 opcionalment → un callback 0.6.0 (5 parts) segueix sent vàlid.
   - Mida màxima estimada: `"1|cl|987654321|b|w|3x3|neon|pill|"` ≈ 31 bytes < 64. OK.
   - Alternativa descartada: camp `style` combinat amb sub-encoding tipus `theme:overlay:preset` — més opac; els camps separats faciliten els botons.

4. **Flux interactiu**:
   - Pas mida: afegir tercera fila amb presets socials (Story, Post, Header, Wallpaper, 4K). En seleccionar un preset, el callback porta `preset=<codi>` i es generen amb els cols/rows/tile_size del preset (els sobreescriu la llibreria); el pas següent (període) segueix igual.
   - Pas nou "Estil" després del període: dues files — 5 temes i 5 overlays — més botó "✨ Skip" a la tercera fila. Botons de tema/overlay són alternants acumulatius (cada clic edita el missatge mostrant la selecció actual i regenera el teclat), el botó Skip dispara la generació amb la selecció feta. La generació final pot ser amb estil per defecte si no s'ha tocat res.
   - `_handle_collage` genera quan `entity+size+period` estan presents; el pas d'estil s'identifica amb `period` present i un flag nou `style_step` implícit: si `theme is None and overlay is None and preset is None` al primer clic post-període → mostrar pas d'estil; els botons d'estil porten `entity,size,period` + camp d'estil corresponent; "Skip" porta `skip=1`? No cal: l'absència de camps d'estil amb un `style_chosen` implícit. **Simplificació**: afegir camp `styled: Optional[bool]`… descartat per complexitat; en lloc d'això, el pas d'estil es dispara amb un callback que inclou `period` però cap camp d'estil, i l'estat "skip" s'identifica perquè el botó Skip codifica `theme="-"` sentinella? **Decisió final (simple i robusta)**: afegir un camp `style: str = ""` amb valor `"skip"` pel botó Skip i `"set"` per indicar "ja s'ha triat estil". Mida total segueix < 64. Flux: `entity,size,period` i `style=""` → pas d'estil; botó tema → `style="set", theme=…`; botó overlay → `style="set", overlay=…`; Skip → `style="skip"`; generació quan `style in ("skip","set")`.
   - Alternativa descartada: 4 passos lineals fixos sense re-selecció — pitjor UX.

5. **Cache persistent al volum de dades**:
   - `CollageService.__init__` rep `cache_dir: Optional[str] = None`; per defecte `config.PROJECT_ROOT / "data" / "collage_cache"` (mateix directori del volum muntat; el mòdul `cache` crea el directori si cal — verificar a la implementació i fer `mkdir(parents=True, exist_ok=True)` preventiu).
   - Alternatives descartades: cache a `/tmp` (no persisteix) o volum nou a compose (innecessari).

6. **Caption**: `build_collage_caption` rep `theme/overlay_style/preset/notext` opcionals i compon `$style_note` (p. ex. `", neon / pill"`, `", preset: instagram-story"`, `", sense text"`). Plantilla `collage_caption` guanya la variable opcional `$style_note` (default buit) — usar `Template.safe_substitute` si no ho fa ja (verificar; el codi actual usa `substitute`, caldrà passar sempre la clau o canviar a safe_substitute).

## Risks / Trade-offs

- [Callback que supera 64 bytes amb owner_id gran + preset llarg] → presets s'envien amb codis curts (`story|post|header|wp|4k`); assert existent a `encode()` ho detectaria en tests.
- [Els canvis de `parse_collage_args` trenquen callers] → refactor complet de callers i tests en el mateix change; `ruff` + suite unittest ho validen.
- [Comportament del pas d'estil en grups] → camps `owner_id` existents ja ho cobreixen; els botons d'estil es codifiquen amb el mateix owner.
- [Cache SQLite en dos processos (bot + admin)] → el mòdul cache usa WAL/thread-lock intern de la llibreria; el risc de corrupció és baix i l'impacte limitat a tiles re-descargats.
- [Telegram limita mida de foto (10 MB)] → el preset 4K (3840x2160 PNG) pot apropar-se al límit; la llibreria ja emet PNG RGB; si supera, Telegram retorna error i el bot mostra el missatge d'error existent. Acceptat com a risc documentat.

## Migration Plan

1. `uv sync` després del bump (resolució idèntica; res migra).
2. Desplegament normal via Docker (rebuild). Callbacks antics pendents de pulsació segueixen sent vàlids (decode tolerant).
3. Rollback: revertir commit i `uv sync`; cap migració de dades (cache és descartable, la DB no canvia).
