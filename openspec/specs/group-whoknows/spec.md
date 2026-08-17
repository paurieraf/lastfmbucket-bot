# group-whoknows Specification

## Purpose
Permetre als membres d'un grup de Telegram consultar el rànquing d'oients d'un artista específic (`/whoknows`, àlies `/wk`), amb resolució canònica a Last.fm, percentatges d'oients, podi i detecció de destronaments.

## Requirements

### Requirement: Automatic Group Membership Discovery
El bot SHALL registrar i actualitzar automàticament la pertinença d'un usuari vinculat a un grup de Telegram (`ChatMember`) quan aquest enviï un missatge o comanda.
- El registre SHALL emmagatzemar `chat_id`, `user_id`, marca de temps `last_active` i booleà `opt_out` (per defecte `False`).

### Requirement: Smart Artist Name Resolution
La comanda `/whoknows` SHALL resoldre el nom de l'artista objectiu seguint aquest ordre de prioritat:
1. **Argument explícit**: Quan l'usuari proporciona un o més arguments (ex: `/whoknows Radiohead`), utilitza el conjunt d'arguments.
2. **Resposta a un missatge**: Quan s'envia com a resposta a un missatge amb informació d'artista o cançó, n'extreu el nom.
3. **Fallback a Now Playing**: Quan no s'especifica cap argument ni és una resposta, consulta el tema que està reproduint l'usuari i n'extreu l'artista.
4. Si no es pot identificar cap artista, el bot SHALL retornar un missatge d'ajuda explicant com especificar un artista.

### Requirement: Last.fm Artist Canonicalization & URL Retrieval
El sistema SHALL validar l'artista amb Last.fm per obtenir el seu nom canònic oficial i la URL web de Last.fm (`https://www.last.fm/music/...`).
- Si Last.fm no reconeix l'artista, el bot SHALL retornar un missatge indicant que no s'ha trobat.

### Requirement: Concurrent Scrobble Playcount Query
El sistema SHALL consultar les reproduccions de tots els membres actius del grup (que no hagin activat l'opt-out) de forma concurrent amb fils asíncrons (`asyncio.gather` + `asyncio.to_thread`) per mantenir el temps de resposta subsegon.
- Els usuaris amb 0 reproduccions per a l'artista SHALL ser exclosos de la llista del podi.
- Si cap membre del grup ha escoltat l'artista, el bot SHALL informar que ningú del grup l'ha escoltat encara.

### Requirement: Rich Ranking Presentation
El bot SHALL formatar el rànquing amb:
- Nom de l'artista amb enllaç HTML a la seva pàgina de Last.fm.
- Nom del grup i total de reproduccions del grup.
- Insígnies de podi (🥇, 🥈, 🥉, 4️⃣, etc.) amb noms d'usuari en negreta i nombre de reproduccions.
- Icona de corona 👑 per al màxim oient.
- Si el líder actual és diferent del posseïdor anterior de la corona en aquest xat, mostrar una notificació de "Destronat" (⚔️ Destronat!).

### Requirement: Now Playing Crown Action Button
La vista del missatge `/np` SHALL incloure un botó inline `👑 Qui ho coneix?` que permeti als membres del grup llançar el rànquing `/whoknows` per a l'artista que està sonant amb un sol toc.
