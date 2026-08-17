# Capability: Group WhoKnows (`/whoknows`, `/wk`)

## ADDED Requirements

### Requirement: Automatic Group Membership Discovery
The bot MUST automatically record and update a user's membership in a Telegram group (`ChatMember`) whenever a linked user sends a message or invokes a command within that chat.
- The record MUST store `chat_id`, `user_id`, `last_active` timestamp, and `opt_out` boolean (default `False`).

### Requirement: Smart Artist Name Resolution
The `/whoknows` command MUST resolve the target artist name according to the following precedence:
1. **Explicit argument**: When the user provides one or more arguments (e.g. `/whoknows Radiohead`), use the combined argument string.
2. **Reply to message**: When the command is sent as a reply to a message containing artist or track information, extract the artist name from the referenced message.
3. **Now Playing fallback**: When no argument is provided and not in reply, fetch the calling user's currently playing track and extract the artist name.
4. If no artist can be identified, the bot MUST return a helpful prompt explaining how to specify an artist.

### Requirement: Last.fm Artist Canonicalization & URL Retrieval
The system MUST validate the artist with Last.fm to obtain the official canonical artist name and Last.fm web URL (`https://www.last.fm/music/...`).
- If Last.fm does not recognize the artist, return a friendly error message indicating the artist was not found.

### Requirement: Concurrent Scrobble Playcount Query
The system MUST query the playcounts of all active, non-opt-out group members concurrently using asynchronous worker threads (`asyncio.gather` + `asyncio.to_thread`) to ensure response time remains sub-second.
- Users with 0 scrobbles for the artist MUST be excluded from the podium display list.
- If no members in the group have scrobbled the artist, the bot MUST inform the chat that nobody in this group has listened to the artist yet.

### Requirement: Rich Ranking Presentation
The bot MUST format the ranking with:
- Artist name formatted as a clickable HTML link to their Last.fm page.
- Group name and total group scrobbles.
- Podium badges (🥇, 🥈, 🥉, 4️⃣, etc.) with bold usernames and playcounts.
- Crown icon 👑 for the top listener.
- If the current leader is different from the previous crown holder in this chat, display a prominent "Dethroned" (⚔️ Destronat!) notification.

### Requirement: Now Playing Crown Action Button
The `/np` message view MUST include an inline button `👑 Qui ho coneix?` (or `👑 Who knows?`) allowing group members to trigger the `/whoknows` ranking for the playing artist with a single tap.
