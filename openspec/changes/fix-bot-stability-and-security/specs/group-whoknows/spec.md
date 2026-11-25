# group-whoknows Delta Specification

## MODIFIED Requirements

### Requirement: Automatic Group Membership Discovery
The bot SHALL register and refresh a linked user's group membership (`ChatMember`) both on bot commands and passively on regular non-command messages in group chats, storing `chat_id`, `user_id`, `last_active`, and `opt_out` without creating placeholder rows for bots or unlinked users during passive message handling.

#### Scenario: Linked user sends a regular message in a group chat
- **WHEN** a user with a linked Last.fm account sends a non-command message in a group or supergroup
- **THEN** the passive group message handler registers or updates their `ChatMember` entry so they appear in `/whoknows` queries

#### Scenario: Bot or unlinked user sends a regular message in a group chat
- **WHEN** a bot account or a Telegram user without a linked Last.fm account sends a regular group message
- **THEN** the passive group message handler ignores the message without writing a placeholder `User` or `ChatMember` row

### Requirement: Last.fm Artist Canonicalization & URL Retrieval
The system SHALL validate the requested artist against Last.fm using canonical capitalization (`properly_capitalized=True`) to obtain its official name and Last.fm URL, returning `None` when Last.fm reports the artist does not exist.

#### Scenario: Valid artist with non-canonical casing
- **WHEN** a user runs `/whoknows radiohead`
- **THEN** Last.fm validates the artist and returns the canonical name (`Radiohead`) and its Last.fm URL

#### Scenario: Unknown artist queried
- **WHEN** a user runs `/whoknows NonExistentBandXYZ` and Last.fm raises `WSError`
- **THEN** the system returns `None` and replies that the artist could not be found on Last.fm

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
