# Design: Actualització de lastfmcollagegenerator v0.6.0 i Comanda /collage

## Context
`lastfmcollagegenerator` ha passat de la versió 0.5.0 a la 0.6.0, introduint matrius arbitràries NxM de fins a 20x20 caselles (límit màxim de 400), resolució dinàmica automàtica (300px per a $\le 5\times 5$, 150px per a $\le 10\times 10$, 100px per a $> 10\times 10$), i control de `tile_size` explícit.

## Arquitectura dels Canvis

### 1. Parser d'Arguments (`parse_collage_args`)
L'analitzador d'arguments a `src/services.py`:
- Reconeix expressions de dimensions `NxM` (ex: `10x10`, `10x5`, `20x20`) i dimensions úniques `N` (`10` $\to$ `10x10`).
- Valida que $1 \le \text{cols} \le 20$, $1 \le \text{rows} \le 20$ i $\text{cols} \times \text{rows} \le 400$.
- Reconeix paràmetres de resolució de casella: `150px`, `ts:150`, `size=150`, `tile_size:150` verificant $50 \le \text{tile\_size} \le 600$.
- Retorna `(entity, cols, rows, period, tile_size)`.

### 2. CollageService
`CollageService.generate_collage_image`:
- Rep `tile_size: Optional[int] = None`.
- Executa de manera no bloquejant `asyncio.to_thread(self._generator.generate, entity=entity, username=username, cols=cols, rows=rows, period=period, tile_size=tile_size)`.
- Retorna un `BytesIO` amb el format PNG.

### 3. Interfície Interactiva (ViewService)
`ViewService.build_collage_selection_response`:
- Ofereix 2 files de selecció de mides:
  - Fila 1: `3x3`, `4x4`, `5x5`
  - Fila 2: `3x5`, `10x5`, `10x10`
- Manté la compatibilitat de `Callback` dins del límit de 64 bytes per a Telegram.
