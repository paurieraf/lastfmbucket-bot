# Tasks: Actualització de lastfmcollagegenerator v0.6.0 i Comanda /collage

- [x] Actualitzar la dependència `lastfmcollagegenerator` a `>=0.6.0` a `pyproject.toml` <!-- id: 1 -->
- [x] Executar `uv lock --upgrade-package lastfmcollagegenerator` i `uv sync` <!-- id: 2 -->
- [x] Ampliar `parse_collage_args` a `src/services.py` per acceptar graelles fins a 20x20 (màx 400 caselles) i `tile_size` (50–600px) <!-- id: 3 -->
- [x] Actualitzar `CollageService.generate_collage_image` per suportar el paràmetre `tile_size` <!-- id: 4 -->
- [x] Ampliar els presets interactius a `ViewService.build_collage_selection_response` amb `3x3`, `4x4`, `5x5`, `3x5`, `10x5`, `10x10` <!-- id: 5 -->
- [x] Actualitzar el handler `/collage` a `src/commands.py` per rebre `tile_size` <!-- id: 6 -->
- [x] Actualitzar la suite de proves a `src/tests.py` cobrint graelles grans, `tile_size`, i nous presets <!-- id: 7 -->
- [x] Actualitzar la documentació del projecte (`README.md`, `ARCHITECTURE.md`, `CONTEXT.md`, `PROJECT.md`, `CHANGELOG.md`, `docs/PRODUCT_PRESENTATION.md`) <!-- id: 8 -->
- [x] Validar amb `uv run python src/tests.py` i `uv run ruff check src/` <!-- id: 9 -->
