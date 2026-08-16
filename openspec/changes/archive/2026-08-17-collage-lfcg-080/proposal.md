# Proposal: collage-lfcg-080

## Why

La llibreria `lastfmcollagegenerator` ha publicat la versió 0.8.0 amb noves capacitats de renderitzat (temes, estils d'overlay, presets de xarxes socials, geometria de caselles, cache persistent d'artwork i resiliencia HTTP). El bot està ancorat a la 0.6.0 i no exposa cap d'aquestes funcionalitats a `/collage`.

## What Changes

- Actualitzar la dependència `lastfmcollagegenerator` de `>=0.6.0` a `>=0.8.0` a `pyproject.toml` i regenerar `uv.lock` (`uv sync`). Sense risc de conflicte: els pins de dependències de la 0.8.0 són idèntics als de la 0.6.0.
- `CollageService.generate_collage_image` acceptarà i passarà a `CollageGenerator.generate()` els nous paràmetres: `theme`, `overlay_style`, `show_text`, `preset`, `cache_dir`, `cache_ttl_override`, `rate_limit`, `fallback_style`, `corner_radius`, `border_width`, `border_color`, `spacing`.
- Cache d'artwork persistent: `CollageService` usarà `data/collage_cache/` com a `cache_dir` (persistit pel volum `./data` de docker-compose; zero canvis d'infraestructura).
- `parse_collage_args` retornarà un dataclass `CollageOptions` (abans tupla) i acceptarà nous arguments CLI: `theme:<x>`, `overlay:<x>`, `notext`, `preset:<x>` (àlies curts), `corner:<n>`, `border:<n>`, `border_color:<hex>`, `spacing:<n>`, `fallback:<gradient|black>`. **BREAKING** pel codi intern que consumeix la tupla (no per als usuaris del bot).
- Protocol de callbacks: afegir camps opcionals `theme`, `overlay`, `preset` al `Callback` (parts 6-8 de l'encoding, mantenint el límit de 64 bytes i compatibilitat de decode amb callbacks antics).
- Assistent interactiu: nou pas "Estil" (temes i overlays amb botó "Skip") i una fila de presets socials al pas de mida.
- Caption: mostrar tema/overlay/preset quan no siguin els valors per defecte.
- Tests unitaris actualitzats (parser, service, callbacks, captions) i entrada nova al `CHANGELOG.md`.

## Capabilities

### New Capabilities

*(cap)*

### Modified Capabilities

- `collage-generation`: ampliar els requeriments de la comanda `/collage` amb els nous paràmetres de renderitzat (tema, overlay, presets, geometria) i el pas interactiu d'estil.

## Impact

- `pyproject.toml`, `uv.lock` (dependència).
- `src/services.py`: `CollageService`, `parse_collage_args`, `build_collage_caption`, `build_collage_selection_response` (dataclass `CollageOptions`).
- `src/commands.py`: handlers `collage` i `_handle_collage` (kwargs nous, pas interactiu d'estil).
- `src/callbacks.py`: `Callback` amb camps nous.
- `src/responses.py`: plantilles de caption i missatges de selecció/ús.
- `src/tests.py`: actualització i ampliació de tests.
- `CHANGELOG.md`: entrada d'usuari.
- `data/collage_cache/`: nou directori de cache (creat en runtime).
