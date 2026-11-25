# crowns-hall-of-fame Specification

## Purpose
Permetre als membres d'un grup de Telegram consultar el Saló de la Fama de les corones d'artistes del xat (`/crowns`) i les corones que ostenta un membre concret (`/crowns @usuari` o `/mycrowns`), amb opció d'opt-out per a privacitat.

## Requirements

### Requirement: Persistent Crown Tracking
The database SHALL maintain a unique `Crown` record per `(chat_id, artist_name)` storing `chat_id`, `artist_name`, `artist_url`, `user_id`, `playcount`, and `updated_at`, and upserting a crown SHALL preserve existing chat metadata (`telegram_chat_name` and `chat_type`).

#### Scenario: Upserting a crown in an existing named group
- **WHEN** `upsert_crown` records or updates a crown for a chat that already has a stored name and type
- **THEN** the crown is saved and the chat's `telegram_chat_name` and `chat_type` remain unchanged

### Requirement: Group Crowns Leaderboard (`/crowns`)
Quan s'invoca `/crowns` sense arguments d'usuari en un grup, el bot SHALL renderitzar el Saló de la Fama del grup ordenat pel recompte de corones d'artistes diferents per membre.

#### Scenario: Group has crowns
- **WHEN** s'invoca `/crowns` en un xat amb corones registrades
- **THEN** cada entrada mostra la insígnia de rang, el nom d'usuari, el recompte total de corones i una mostra dels artistes coronats

#### Scenario: Group has no crowns yet
- **WHEN** s'invoca `/crowns` en un xat sense cap corona
- **THEN** el bot mostra un missatge engrescador per utilitzar `/whoknows`

### Requirement: User Crowns Inspection (`/crowns @username` / `/mycrowns`)
When `/crowns @username` or `/mycrowns` is invoked, the bot SHALL return the user's crowns in the current chat with HTML-escaped artist names, links, and playcounts, truncating cleanly before Telegram's 4096-character limit with a `... and N more crowns` footer when needed.

#### Scenario: User holds many crowns exceeding Telegram's message limit
- **WHEN** a user with dozens or hundreds of crowns invokes `/mycrowns` or `/crowns @username`
- **THEN** the formatted message stays within 4096 characters and appends `... and N more crowns` indicating how many crowns were omitted

#### Scenario: User holds no crowns in the chat
- **WHEN** a user with zero crowns in the chat invokes `/mycrowns`
- **THEN** the bot returns an explanatory message with HTML-escaped user and chat names

### Requirement: Privacy Opt-Out
Users SHALL be able to toggle their group ranking visibility in `/preferences` using English labels (`🔒 Hide me from group rankings` / `🔓 Show me in group rankings`), excluding opted-out users from `/whoknows` and `/crowns`.

#### Scenario: User toggles group ranking visibility in `/preferences`
- **WHEN** the owning user clicks the opt-out toggle button in `/preferences`
- **THEN** the bot flips `group_opt_out`, updates their `ChatMember` records, and displays English confirmation feedback
