# group-whoknows Specification

## Purpose
Permetre als membres d'un grup de Telegram consultar el rànquing d'oients d'un artista específic (`/whoknows`, àlies `/wk`), amb resolució canònica a Last.fm, percentatges d'oients, podi i detecció de destronaments.

## Requirements

### Requirement: Automatic Group Membership Discovery
The bot SHALL register and refresh a linked user's group membership (`ChatMember`) both on bot commands and passively on regular non-command messages in group chats, storing `chat_id`, `user_id`, `last_active`, and `opt_out` without creating placeholder rows for bots or unlinked users during passive message handling.

#### Scenario: Linked user sends a regular message in a group chat
- **WHEN** a user with a linked Last.fm account sends a non-command message in a group or supergroup
- **THEN** the passive group message handler registers or updates their `ChatMember` entry so they appear in `/whoknows` queries

#### Scenario: Bot or unlinked user sends a regular message in a group chat
- **WHEN** a bot account or a Telegram user without a linked Last.fm account sends a regular group message
- **THEN** the passive group message handler ignores the message without writing a placeholder `User` or `ChatMember` row

### Requirement: Smart Artist Name Resolution
La comanda `/whoknows` SHALL resoldre el nom de l'artista objectiu per ordre de prioritat: argument explícit, resposta a un missatge musical, o fallback al Now Playing de l'usuari.

#### Scenario: Explicit artist argument provided
- **WHEN** l'usuari executa `/whoknows Radiohead`
- **THEN** el bot utilitza els arguments com a nom d'artista

#### Scenario: Replied message or Now Playing fallback
- **WHEN** no es passa cap argument però es respon a un missatge o l'usuari reprodueix música
- **THEN** el bot extreu l'artista de la resposta o del Now Playing

#### Scenario: No artist can be determined
- **WHEN** no hi ha argument, ni resposta, ni Now Playing actiu
- **THEN** el bot retorna un missatge d'ajuda explicant com especificar un artista

### Requirement: Last.fm Artist Canonicalization & URL Retrieval
The system SHALL validate the requested artist against Last.fm using canonical capitalization (`properly_capitalized=True`) to obtain its official name and Last.fm URL, returning `None` when Last.fm reports the artist does not exist.

#### Scenario: Valid artist with non-canonical casing
- **WHEN** a user runs `/whoknows radiohead`
- **THEN** Last.fm validates the artist and returns the canonical name (`Radiohead`) and its Last.fm URL

#### Scenario: Unknown artist queried
- **WHEN** a user runs `/whoknows NonExistentBandXYZ` and Last.fm raises `WSError`
- **THEN** the system returns `None` and replies that the artist could not be found on Last.fm

### Requirement: Concurrent Scrobble Playcount Query
El sistema SHALL consultar les reproduccions de tots els membres actius del grup (sense opt-out) de forma concurrent (`asyncio.gather` + `asyncio.to_thread`), excloent els oients amb 0 reproduccions.

#### Scenario: Listeners with scrobbles ranked
- **WHEN** un o més membres del grup tenen reproduccions > 0 per a l'artista
- **THEN** els oients amb 0 reproduccions s'exclouen i la resta s'ordenen de més a menys

#### Scenario: No group listeners
- **WHEN** cap membre del grup ha escoltat l'artista
- **THEN** el bot informa que ningú del grup l'ha escoltat encara

### Requirement: Rich Ranking Presentation
The bot SHALL format the ranking with HTML-escaped artist name, chat name, usernames, and URL attributes, podium badges, crown icon for the leader, group totals, and an English dethronement banner (`⚔️ NEW BAND KING!`) when the crown changes hands.

#### Scenario: Crown holder is dethroned
- **WHEN** a `/whoknows` query finds a new top listener different from the previous crown holder
- **THEN** the response displays an English dethronement banner (`⚔️ NEW BAND KING!`) with properly HTML-escaped usernames and playcounts

### Requirement: Now Playing Crown Action Button
The `/np` message view SHALL include an inline button labeled `👑 Who knows?` that any member of the chat can press to run `/whoknows` for the currently playing artist.

#### Scenario: Group member clicks the WhoKnows button on `/np`
- **WHEN** any user in the group clicks `👑 Who knows?` on a `/np` message
- **THEN** the bot resolves the owner's currently playing artist and replies with the group `/whoknows` ranking
