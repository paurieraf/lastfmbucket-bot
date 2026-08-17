# Capability: Crowns Hall of Fame (`/crowns`, `/mycrowns`)

## ADDED Requirements

### Requirement: Persistent Crown Tracking
The database MUST maintain a `Crown` record for each unique combination of `(chat_id, artist_name)`.
- Each record MUST store `chat_id`, `artist_name`, `artist_url`, `user_id` (current leader), `playcount`, and `updated_at`.
- Whenever a `/whoknows` query determines a new non-zero leader, the database record MUST be inserted or updated.

### Requirement: Group Crowns Leaderboard (`/crowns`)
When `/crowns` is invoked without user arguments in a group chat, the bot MUST render the Group Hall of Fame:
- Ranked list of group members ordered by the count of distinct artist crowns held in this chat.
- Each entry MUST show the member's rank badge, Telegram display name, total crown count, and a sample of top crowned artists.
- If no crowns have been awarded yet in this chat, display a friendly prompt encouraging users to use `/whoknows`.

### Requirement: User Crowns Inspection (`/crowns @username` / `/mycrowns`)
When `/crowns` is invoked with a specific user mention or `/mycrowns` is used:
- Return all artist crowns held by that user in the current chat.
- Each crowned artist MUST include the artist name (linked to Last.fm) and the scrobble count.
- If the user holds 0 crowns, display an encouraging message to discover new artists and win crowns.

### Requirement: Privacy Opt-Out
Users MUST be able to toggle their group ranking visibility via `/preferences`.
- When `opt_out` is `True`, the user MUST NOT appear in `/whoknows` charts, `/crowns` leaderboards, or hold crowns in group chats.
