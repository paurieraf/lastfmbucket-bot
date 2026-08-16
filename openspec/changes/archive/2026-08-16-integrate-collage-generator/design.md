## Context

Veure `proposal.md` per a la motivació.

El bot està desenvolupat sobre `python-telegram-bot` v22.5 amb un paradigma totalment asíncron (`async`/`await`). La biblioteca `lastfmcollagegenerator` v0.5.0 utilitza operacions síncrones de descàrrega HTTP (`requests`) i renderització de vectors/píxels (`Pillow`). Per tant, cal aïllar l'execució de la generació de collages en un fil secundari per no bloquejar l'event loop del bot de Telegram.

## Goals / Non-Goals

**Goals:**
- Integrar `lastfmcollagegenerator.CollageGenerator` de forma neta i desacoblada a la capa de serveis (`CollageService` / `LastfmService`).
- Executar les crides de generació en segon pla mitjançant `asyncio.to_thread()`.
- Proporcionar la comanda `/collage` amb suport per a arguments lliures (ex. `/collage 3x3 week album`) i valors per defecte (`3x3`, `7day`, `album`).
- Oferir una navegació interactiva via Inline Keyboard per triar entitat, dimensions i període.
- Convertir la imatge `PIL.Image` generada a `io.BytesIO` en memòria i enviar-la amb `reply_photo` o `send_photo`.
- Mostrar un indicador visual de càrrega (`ChatAction.UPLOAD_PHOTO` o missatge temporal) mentre es genera el collage.

**Non-Goals:**
- Generació de collages animats o formats fora de la graella matricial fins a 5x5.
- Emmagatzematge permanent en disc de les imatges generades (es processen 100% en memòria per estalviar espai).

## Decisions

1. **Capa de Serveis (`CollageService` a `src/services.py`):**
   - S'instancia `CollageGenerator(api_key, api_secret)` aprofitant les credencials ja existents a `config.py`.
   - Mètode `generate_collage(username, entity, cols, rows, period) -> io.BytesIO` que encapsula la crida i la conversió a bytes PNG/JPEG.
   - *Alternativa descartada*: Cridar `CollageGenerator` directament des de `commands.py`. S'ha descartat per mantenir la separació de responsabilitats i la consistència arquitectònica amb `LastfmService` i `ViewService`.

2. **Aïllament Asíncron (`asyncio.to_thread`):**
   - Com que `CollageGenerator.generate()` fa múltiples requests síncrons i operacions CPU-heavy de PIL, s'executa amb `await asyncio.to_thread(self._generator.generate, ...)`.
   - *Alternativa descartada*: Fer servir Celery o Redis Queue. Resultaria en sobreenginyeria innecessària donada la càrrega del bot.

3. **Flexibilitat en el Parser d'Arguments (`_parse_collage_args`):**
   - El parser reconeixerà patrons en qualsevol ordre:
     - Dimensions: `(\d+)x(\d+)` (ex. `3x3`, `5x5`, `4x4`) limitades a mínim 1x1 i màxim 5x5.
     - Entitats: `album|albums`, `artist|artists`, `track|tracks|song|songs`.
     - Períodes: `7d|7day|week`, `1m|1month|month`, `3m|3month`, `6m|6month`, `1y|1year|year`, `overall|all|alltime`.
   - Si no s'especifica algun paràmetre, s'aplica el defecte: `cols=3, rows=3, entity="album", period="7day"`.

4. **Protocol de Callback Telegram (`callbacks.py`):**
   - S'afegeix l'acció `Action.COLLAGE = "cl"` a `callbacks.py`.
   - Es codifica l'estat mantenint la restricció estricta de 64 bytes de Telegram (`v|action|owner_id|entity|period|size`).

## Risks / Trade-offs

- **[Risc: Retards de xarxa o scraping d'imatges de Last.fm]** → *Mitigació*: `lastfmcollagegenerator` ja té timeouts definits i fallbacks automàtics a rajoles negres si una imatge no es troba o falla. A més, el bot mostra `send_chat_action(ChatAction.UPLOAD_PHOTO)` per donar feedback immediat a l'usuari.
- **[Risc: Consum de memòria amb graelles 5x5 concurrents]** → *Mitigació*: Els buffers `io.BytesIO` s'alliberen automàticament un cop enviada la foto a Telegram; una graella 5x5 (1500x1500px) requereix menys de 3MB de RAM en memòria.
