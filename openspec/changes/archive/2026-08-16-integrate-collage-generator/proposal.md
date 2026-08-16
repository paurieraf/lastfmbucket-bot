## Why

Amb la publicació de `lastfmcollagegenerator` v0.5.0, disposem d'un generador de collages robust i flexible que suporta la creació de graelles visuals (des d'1x1 fins a 5x5) per a àlbums, artistes i cançons sobre qualsevol període de Last.fm (`7day`, `1month`, `3month`, `6month`, `12month`, `overall`), amb overlay de playcounts i gestió resilient d'imatges/fallbacks. Integrar aquesta funcionalitat al bot de Telegram (`lastfmbucket-bot`) permet als usuaris generar i compartir fàcilment collages musicals directament als seus xats i grups.

## What Changes

- Afegir la comanda `/collage` al bot de Telegram amb suport per a paràmetres directes (ex. `/collage 3x3 week album`) i mode interactiu amb botons inline.
- Implementar `CollageService` per gestionar la generació de collages en un fil asíncron (`asyncio.to_thread`) i enviar la imatge resultante (`send_photo`) al xat de Telegram.
- Integrar opcions de collage amb suport per a tipus d'entitat (àlbums, artistes, cançons), dimensions (graelles de fins a 5x5, per defecte 3x3 o 5x5) i períodes temporals.
- Actualitzar `callbacks.py` amb accions d'inline keyboard per navegar i seleccionar tipus d'entitat, mida i període de collage sense sortir de Telegram.
- Actualitzar `/help` i documentació del bot per reflectir la nova comanda `/collage`.

## Capabilities

### New Capabilities
- `collage-generation`: Generació i enviament de graelles visuals (collages) de tops d'àlbums, artistes i cançons mitjançant `lastfmcollagegenerator`, amb flux interactiu i suport de comanda amb arguments.

### Modified Capabilities

## Impact

- **Dependències**: S'utilitza `lastfmcollagegenerator>=0.5.0` (amb `Pillow`, `beautifulsoup4`, `requests`, `html5lib`).
- **Codi font**: 
  - Nou o ampliat `CollageService` a `src/services.py`.
  - Nous handlers de comanda `/collage` i callbacks a `src/commands.py` i `src/callbacks.py`.
  - Registre del handler i configuració a `src/bot.py`.
  - Respostes i missatges a `src/responses.py`.
- **Rendiment**: L'execució de descàrrega i composició gràfica s'executa en segon pla per no bloquejar l'event loop asíncron del bot.
