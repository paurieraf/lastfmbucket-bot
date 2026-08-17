## 1. Setup

- [x] 1.1 Bump `lastfmcollagegenerator` version to `>=1.3.0` in `pyproject.toml`
- [x] 1.2 Run `uv sync` to update the `uv.lock` file and install the new version

## 2. Core Implementation

- [x] 2.1 Refactor `CollageService.generate_collage_image` (i crides dependents) per ser totalment asíncron, utilitzant `await self._generator.generate_async()`
- [x] 2.2 Eliminar qualsevol referència a `asyncio.to_thread` per a la generació de collages dins dels serveis
- [x] 2.3 Adaptar la lògica d'exportació de `CollageService` per utilitzar `export_image` de la llibreria i generar fitxers WebP o JPEG optimitzats abans d'enviar-los
- [x] 2.4 Fer que `CollageService` accepti els nous kwargs `filters` i `font_bold`

## 3. CLI & Command Parsing

- [x] 3.1 Actualitzar l'expressió regular i el parser a `parse_collage_args` (`src/commands.py`) per reconèixer i extreure `filter:(.*)`
- [x] 3.2 Actualitzar `parse_collage_args` per extreure i activar el flag `bold`
- [x] 3.3 Adaptar el flux interactiu d'inline keyboards si és necessari perquè transmeti els nous arguments per defecte en ometre l'estil

## 4. Testing & Verification

- [x] 4.1 Validar la generació de `/collage` (amb i sense paràmetres) comprovant que el botó no es bloqueja i que els formats de sortida s'envien correctament a Telegram
- [x] 4.2 Validar `/collage filter:duotone bold` i verificar els resultats visuals
