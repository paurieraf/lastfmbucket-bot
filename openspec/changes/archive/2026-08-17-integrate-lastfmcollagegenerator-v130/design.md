## Context

`lastfmbucket-bot` està construït sobre `python-telegram-bot` amb suport total asíncron (`async`/`await`). Anteriorment, `lastfmcollagegenerator` només proporcionava mètodes síncrons, per la qual cosa `CollageService` utilitzava `asyncio.to_thread` per evitar bloquejar el bucle d'esdeveniments. La nova versió de la llibreria introdueix `generate_async()`, que gestiona nativament la concurrència d'I/O (via `httpx`). Aquest fet permet al bot eliminar el *workaround* de threading. (Veure proposal.md).

## Goals / Non-Goals

**Goals:**
- Substituir l'ús d'`asyncio.to_thread` per la crida asíncrona nativa `generate_async()`.
- Exportar les imatges generades cap a formats optimitzats (ex. WebP/JPEG) mitjançant la nova utilitat de la llibreria abans d'enviar-les via Telegram.
- Integrar les noves funcionalitats visuals (`filter:<nom>` i tipografia `bold`) al parser d'arguments i als teclats interactius.

**Non-Goals:**
- Redissenyar tot el flux interactiu de collages; simplement afegirem un nou pas o botons per a les opcions extra.

## Decisions

- **Canvi a API Asíncrona Nadiua**: `CollageService.generate_collage_image` (o equivalent) cridarà directament a `await self._generator.generate_async(...)`. Aquest canvi requerirà actualitzar qualsevol dependència dins del bot que s'esperés una funció bloquejant.
- **Exportació WebP / JPEG Optimitzat**: Per reduir amplada de banda, s'utilitzarà el mètode de la llibreria `CollageGenerator.export_image` guardant la imatge (en disc temporal o BytesIO) amb un format comprimit abans de pujar-ho amb `send_photo`. WebP és ideal perquè manté transparències i redueix mida.
- **Extensió CLI de `/collage`**: S'ampliarà `parse_collage_args` de `commands.py` per capturar tokens com `filter:duotone` i la flag `bold`. S'afegiran aquests paràmetres a les opcions passades al servei de generació.

## Risks / Trade-offs

- **[Risc: Problemes de rendiment durant l'exportació a WebP]** → *Mitigació*: Si el WebP requereix massa CPU, es pot utilitzar el fall-back de `JPEG` passant un `background_color` per aflattenar el canal alfa segons suporta la pròpia utilitat de la llibreria.
- **[Risc: Incompatibilitats d'API a lastfmcollagegenerator]** → *Mitigació*: Tot i l'evolució, `generate_async` té una signatura paral·lela al clàssic `generate`, reduint problemes de refactor.
