## Why

En els grups de Telegram on es comparteix música, les consultes individuals com `/np` o `/tops` sovint generen converses sobre qui és més fan d'un determinat artista o grup. Actualment, el bot no disposa de cap mecanisme per comparar l'escolta col·lectiva d'una banda dins d'un xat ni per fomentar la gamificació social. La introducció del sistema `/whoknows` (i el Saló de les Corones `/crowns`) converteix el bot en un dinamitzador comunitari clau, permetent coronar el màxim oient de cada artista al grup i detectar destronaments en temps real.

## What Changes

- **Nou model de base de dades `ChatMember`**: Registre automàtic i transparent de la pertinença d'usuaris vinculats als xats de grup quan interactuen amb el bot, incloent preferència de privacitat (`opt_out`).
- **Nou model de base de dades `Crown`**: Persistència del líder actual de cada artista per xat (`chat_id`, `artist_name`, `artist_url`, `user_id`, `playcount`, `updated_at`).
- **Canonització i resolució d'artistes**: Obtenció del nom oficial i URL canònica de Last.fm (`Artist.get_name()`, `Artist.get_url()`) per evitar duplicats per majúscules/minúscules o variants tipogràfiques.
- **Nova comanda `/whoknows` (àlies `/wk`)**:
  - Resolució intel·ligent de l'artista: argument explícit, per resposta (reply) a un missatge anterior, o per defecte el que està sonant a `/np`.
  - Consultes concurrents en paral·lel (`asyncio.gather` + `asyncio.to_thread`) per consultar els scrobbles de tots els membres del grup sense bloquejar l'event loop.
  - Filtratge automàtic d'usuaris amb 0 scrobbles o que han activat l'`opt_out`.
  - Format ric amb podi (🥇, 🥈, 🥉), enllaç web de l'artista a Last.fm, percentatges i avís especial de destronament ⚔️ quan el #1 canvia.
- **Nova comanda `/crowns` (àlies `/mycrowns`)**:
  - Sense arguments: Saló de la Fama del grup (taula de líders amb més corones acumulades).
  - Amb menció `@usuari`: Llista detallada de corones que ostenta aquell usuari al xat.
- **Botó interactiu a `/np`**: Afegir botó inline `👑 Qui ho coneix?` a la vista de Now Playing per saltar directament al `/whoknows` de l'artista actual.
- **Gestió de privacitat a `/preferences`**: Opció interactiva per commutar la visibilitat als rànquings de grup (`opt_out`).
- **Tests unitaris i d'integració**: Cobertura exhaustiva per a resolució d'artistes, rànquings, destronaments i persistència a `src/tests.py`.

## Capabilities

### New Capabilities
- `group-membership-tracking`: Cens automàtic i gestió de membres de grup (`ChatMember`) amb suport de privacitat `opt_out`.
- `group-whoknows`: Rànquing d'scrobbles d'un artista entre els membres d'un grup amb resolució asíncrona paral·lela i resolució canònica a Last.fm.
- `crowns-hall-of-fame`: Sistema de corones per artista, persistència de lideratge, detecció de destronaments i saló de la fama del grup (`/crowns`).

### Modified Capabilities
- `bot-command-handlers`: Registre de noves comandes públiques (`/whoknows`, `/wk`, `/crowns`, `/mycrowns`) i botó de corona a `/np`.
- `user-preferences`: Commutació de privacitat `opt_out` per a rànquings de grup.

## Impact

- **Models de BD**: Nous models `ChatMember` i `Crown` a `src/db.py`.
- **Serveis**: Nous mètodes a `src/lastfm.py` i nou `GroupService` a `src/services.py`.
- **Comandes & Callbacks**: Handlers `/whoknows` i `/crowns` a `src/commands.py`, botons i callbacks a `src/callbacks.py` i plantilles a `src/responses.py`.
- **Tests**: Nous tests a `src/tests.py`.
- **Documentació**: `README.md`, `ARCHITECTURE.md`, `CONTEXT.md`, `PROJECT.md`, `CHANGELOG.md`, `docs/PRODUCT_PRESENTATION.md`.
