## Why

La biblioteca `lastfmcollagegenerator` ha publicat noves versions fins a la 1.3.0, introduint un pipeline totalment asíncron (async/await) de descàrrega i renderitzat, millores en la tipografia, filtres visuals (com el duotone) i un motor d'exportació nadiu (amb suport per WebP i JPEG optimitzats). Actualment, `lastfmbucket-bot` utilitza la versió 0.8.0 i crida el generador utilitzant fils secundaris (`asyncio.to_thread`), fet que suposa un cert overhead i no aprofita les capacitats asíncrones reals, a més de no oferir els nous paràmetres visuals als usuaris.

## What Changes

- S'actualitzarà la dependència `lastfmcollagegenerator` a `>=1.3.0`.
- S'eliminarà l'ús d'`asyncio.to_thread` a `CollageService` per invocar directament el mètode asíncron `self._generator.generate_async()` i similars.
- S'introduiran nous paràmetres opcionals a la comanda `/collage` i a la UI interactiva (per exemple, filtres visuals com `duotone` i tipografia en negreta `bold`).
- S'utilitzarà la utilitat d'exportació nativa de la biblioteca per formatar la imatge abans de ser enviada per Telegram (ex: compressió per estalviar recursos i amplada de banda).

## Capabilities

### New Capabilities
- `collage-advanced-visuals`: Implementació de filtres visuals (ex: duotone) i estils tipogràfics (bold) per a la comanda de collage.
- `collage-async-pipeline`: Integració del generador asíncron natiu (v1.0.0+) i el sistema d'exportació d'imatges.

### Modified Capabilities
- `collage-generation`: S'actualitza el comportament intern per ser natiu asíncron, utilitzar compressió d'imatge i acceptar els nous paràmetres.

## Impact

- `pyproject.toml` i `uv.lock` s'actualitzaran per a `lastfmcollagegenerator>=1.3.0`.
- `src/services.py`: `CollageService` requerirà canvis d'arquitectura per abandonar `asyncio.to_thread` en favor de crides natives `await`, i utilitzarà els nous arguments de configuració.
- `src/commands.py`: S'actualitzarà el parser de paràmetres i els botons/keyboard inlines si cal exposar les opcions de filtre i text.
