## Why

Amb la publicació de `lastfmcollagegenerator` v0.6.0, la llibreria ofereix suport per a graelles arbitràries NxM des d'1x1 fins a 20x20 (fins a 400 caselles), resolució dinàmica adaptativa, paràmetre opcional `tile_size` (50–600px) i escalat tipogràfic proporcional. Cal actualitzar la dependència del bot a la versió 0.6.0 i revisar la comanda `/collage` per oferir aquestes noves possibilitats tant via comanda CLI com a l'assistent interactiu d'inline keyboards.

## What Changes

- Actualitzar la dependència `lastfmcollagegenerator` a `>=0.6.0` a `pyproject.toml` i actualitzar `uv.lock`.
- Ampliar `parse_collage_args` per permetre dimensions fins a 20x20 (màxim 400 caselles) i reconèixer paràmetres de mida de casella (`tile_size`, `150px`, `ts:150`).
- Actualitzar `CollageService.generate_collage_image` per acceptar i propagar `tile_size`.
- Ampliar els presets de selecció interactiva de mides a `ViewService` amb opcions clàssiques i grans (`3x3`, `4x4`, `5x5`, `3x5`, `10x5`, `10x10`).
- Actualitzar la documentació del projecte (`README.md`, `ARCHITECTURE.md`, `CONTEXT.md`, `PROJECT.md`, `CHANGELOG.md`, `docs/PRODUCT_PRESENTATION.md`).
- Afegir tests unitaris exhaustius per a les noves capacitats a `src/tests.py`.

## Capabilities

### New Capabilities
- `collage-arbitrary-grids`: Suport per a graelles rectangulars i quadrades des d'1x1 fins a 20x20 amb un màxim de 400 caselles.
- `collage-tile-sizing`: Suport per a resolució personalitzada de casella (`tile_size` de 50px a 600px).

### Modified Capabilities
- `collage-generation`: Millora de l'assistent interactiu amb nous presets i validacions ampliades.

## Impact

- **Dependències**: `lastfmcollagegenerator` actualitzat a `0.6.0`.
- **Codi font**: `src/services.py`, `src/commands.py`, `src/tests.py`, `pyproject.toml`, `uv.lock`.
- **Documentació**: `README.md`, `ARCHITECTURE.md`, `CONTEXT.md`, `PROJECT.md`, `CHANGELOG.md`, `docs/PRODUCT_PRESENTATION.md`.
