# crowns-hall-of-fame Specification

## Purpose
Permetre als membres d'un grup de Telegram consultar el Saló de la Fama de les corones d'artistes del xat (`/crowns`) i les corones que ostenta un membre concret (`/crowns @usuari` o `/mycrowns`), amb opció d'opt-out per a privacitat.

## Requirements

### Requirement: Persistent Crown Tracking
La base de dades SHALL mantenir un registre `Crown` per a cada combinació única de `(chat_id, artist_name)`.
- Cada registre SHALL guardar `chat_id`, `artist_name`, `artist_url`, `user_id` (líder actual), `playcount` i `updated_at`.
- Quan una consulta de `/whoknows` determina un nou líder amb reproduccions > 0, el registre a la base de dades SHALL ser inserit o actualitzat.

### Requirement: Group Crowns Leaderboard (`/crowns`)
Quan s'invoca `/crowns` sense arguments d'usuari en un grup, el bot SHALL renderitzar el Saló de la Fama del grup:
- Llista classificada de membres del grup ordenada pel recompte de corones d'artistes diferents que ostenten en aquest xat.
- Cada entrada SHALL mostrar la insígnia de rang, el nom d'usuari de Telegram, el recompte total de corones i una mostra dels artistes coronats.
- Si encara no s'ha atorgat cap corona al xat, el bot SHALL mostrar un missatge engrescador per utilitzar `/whoknows`.

### Requirement: User Crowns Inspection (`/crowns @username` / `/mycrowns`)
Quan s'invoca `/crowns` amb la menció d'un usuari específic o s'executa `/mycrowns`:
- Retornar totes les corones d'artistes que té aquell usuari al xat actual.
- Cada artista coronat SHALL incloure el nom de l'artista (enllaçat a Last.fm) i el nombre de reproduccions.
- Si l'usuari no té cap corona, mostrar un missatge explicatiu.

### Requirement: Privacy Opt-Out
Els usuaris SHALL poder commutar la seva visibilitat als rànquings de grup des de `/preferences`.
- Quan `opt_out` és `True`, l'usuari NO SHALL aparèixer a les taules de `/whoknows`, ni als rànquings de `/crowns`, ni podrà ostentar corones en xats de grup.
