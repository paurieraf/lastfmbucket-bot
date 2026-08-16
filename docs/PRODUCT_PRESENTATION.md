# 🎵 lastfmbucket-bot — Product Presentation

> *Your Last.fm listening history, reimagined for Telegram and supercharged with AI.*

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [Who Is It For?](#2-who-is-it-for)
3. [Feature Showcase](#3-feature-showcase)
4. [User Journeys](#4-user-journeys)
5. [System at a Glance](#5-system-at-a-glance)
6. [AI Capabilities](#6-ai-capabilities)
7. [Admin & Operations](#7-admin--operations)
8. [Privacy & Data](#8-privacy--data)

---

## 1. Product Vision

**lastfmbucket-bot** transforms passive music scrobbling into an active, social experience inside Telegram.

Most people who use Last.fm treat it as a silent ledger — data collected, rarely surfaced. This bot inverts that: it meets listeners where they already spend their time (Telegram), pipes in their live scrobble history, and layers on **AI-generated personality insights** that make music taste feel personal and expressive.

It's designed to be self-hosted, privacy-first, and free from external AI API costs — running entirely with a local LLM (Ollama + qwen2.5:0.5b).

```mermaid
mindmap
  root((lastfmbucket-bot))
    Listening Intelligence
      Now Playing card
      Recent Tracks timeline
      Interactive Top Charts
        Artists
        Albums
        Tracks
        6 Time Periods
    Social Features
      Share what you're hearing
      Compare with friends
      Group chat support
    AI Insights
      Vibe analysis
      Music taste roast
      Artist recommendations
    Administration
      Web admin panel
      Command audit logs
      User management
```

---

## 2. Who Is It For?

| Persona | How They Use It |
|---------|----------------|
| 🎧 **Music Enthusiasts** | Share now-playing cards in group chats; explore personal taste trends |
| 👥 **Friend Groups** | Compare listening habits; discover shared artists |
| 🎵 **Last.fm Power Users** | Surface their scrobble data directly in the messenger they already use |
| 🤖 **AI-Curious Users** | Get playful AI commentary on their musical identity — no cloud API needed |
| 🖥️ **Self-Hosters** | Deploy on a VPS with full control over their data |

---

## 3. Feature Showcase

### 3.1 Now Playing — `/np`

The flagship command. Fetches the user's currently scrobbling track from Last.fm in real time and renders a rich message card.

**What you get:**
- Track title, artist, and album name
- An interactive **"More info"** button that expands to the last 5 tracks
- An **album cover art** button that replaces the text card with a full photo

```mermaid
sequenceDiagram
    actor User
    participant Bot
    participant LastFM as Last.fm API

    User->>Bot: /np
    Bot->>LastFM: getRecentTracks(limit=1)
    LastFM-->>Bot: Current track + nowplaying flag
    Bot-->>User: 🎵 Track Card + [More info] [🖼️ Cover]

    User->>Bot: [🖼️ Cover] button
    Bot->>LastFM: album.getInfo() → cover URL
    LastFM-->>Bot: Album artwork URL
    Bot-->>User: Photo card with caption
```

---

### 3.2 Recent Tracks — `/status`

Shows the last 5 scrobbled tracks with **human-readable relative timestamps** ("3 minutes ago", "yesterday"). Clicking the **"Less info"** button collapses back to the compact Now Playing view.

---

### 3.3 Interactive Top Charts — `/tops`

The most interactive feature. A multi-step inline keyboard navigation:

```mermaid
flowchart LR
    A["/tops command"] --> B{"Select entity"}
    B --> C["🎤 Artists"]
    B --> D["💿 Albums"]
    B --> E["🎵 Tracks"]
    C --> F{"Select period"}
    D --> F
    E --> F
    F --> G["7 Days"]
    F --> H["1 Month"]
    F --> I["3 Months"]
    F --> J["6 Months"]
    F --> K["1 Year"]
    F --> L["Overall"]
    G --> M["📊 Top 10 List"]
    H --> M
    I --> M
    J --> M
    K --> M
    L --> M
```

You can also skip the menus with a direct command:
```
/tops artists week
/tops albums month
/tops tracks overall
```

**Group chat safety:** The 64-byte callback payload always encodes the *owner's* Telegram ID, ensuring that other group members pressing your buttons only refresh *your* data — not their own.

---

### 3.4 Visual Collage Generation — `/collage`

Generates high-resolution composite image cards of your top albums, artists, or tracks:

- **Configurable Dimensions:** Supports arbitrary NxM grids from 1x1 up to **20x20** (maximum 400 tiles).
- **Dynamic Resolution Scaling:** Automatically scales tile resolutions (300px, 150px, 100px) and font typography proportionally for crystal-clear visual quality without excessive memory usage.
- **Custom Tile Sizing:** Optionally specify explicit tile sizes (e.g. `150px`, `ts:200`) between 50px and 600px.
- **Interactive Multi-Tier Builder or CLI Shortcuts:**
  ```
  /collage                         # Launches interactive 3-step button builder
  /collage 3x3 week album          # Direct 3x3 weekly album collage
  /collage 10x10 overall artist    # Massive 100-artist all-time collage
  /collage 5x5 1month track 150px  # 25-track monthly collage with custom 150px tiles
  ```

```mermaid
flowchart LR
    A["/collage command"] --> B{"Select entity"}
    B --> C["👤 Artist"]
    B --> D["💿 Album"]
    B --> E["🎵 Track"]
    C --> F{"Select grid size"}
    D --> F
    E --> F
    F --> G["3x3, 4x4, 5x5..."]
    F --> H{"Select period"}
    G --> H
    H --> I["🎨 Generated Collage Photo"]
```

---

### 3.5 User Comparison — `/compare <lastfm_username>`

Compare your listening stats head-to-head with any Last.fm user:

- **Scrobble count** for each user
- **Top 5 artists** side-by-side
- **Common artists** — artists you both love, with each person's play counts

```mermaid
sequenceDiagram
    actor User
    participant Bot
    participant LastFM as Last.fm API

    User->>Bot: /compare rockfan99
    Bot->>LastFM: getInfo(user1) + getTopArtists(user1)
    Bot->>LastFM: getInfo(user2) + getTopArtists(user2)
    Bot->>LastFM: getTopArtists(user1, limit=50)
    Bot->>LastFM: getTopArtists(user2, limit=50)
    LastFM-->>Bot: Stats + artist lists
    Bot-->>User: 📊 Comparison table with shared artists
```

---

### 3.5 Preferences — `/preferences`

Shows the user's linked Last.fm account and provides an **Unlink account** inline button that removes the Telegram ↔ Last.fm mapping from the database with a single tap.

---

## 4. User Journeys

### 4.1 Onboarding Flow

```mermaid
journey
    title New User Onboarding
    section Discovery
      User finds bot in Telegram: 5: User
      Sends /start command: 5: User, Bot
      Receives welcome message: 4: Bot
    section Setup
      User sends /set johndoe: 5: User
      Bot links Telegram ID to Last.fm username: 5: Bot
      Bot confirms account linked: 5: Bot
    section First Use
      User sends /np: 5: User
      Bot returns now playing card: 5: Bot
      User taps album cover button: 4: User
      Bot shows album artwork: 5: Bot
    section Exploration
      User tries /tops: 5: User
      User navigates Artists → 1 Month: 4: User
      User shares with group: 5: User
```

### 4.2 Social Group Chat Flow

```mermaid
journey
    title Friends Discovering Shared Music
    section Setup
      All members link their Last.fm in DMs with /set: 5: User
    section Daily Use
      Member A shares /np in group: 5: User
      Other members see what's playing: 4: Group
      Member B uses /compare membera_lastfm: 5: User
      Group discusses shared artists: 5: Group
    section AI Fun
      User requests /roast: 5: User
      Bot delivers humorous AI critique: 5: Bot
      Group reacts and laughs: 5: Group
      Another user requests /recommend: 4: User
      Discovers new artist: 5: User
```

---

## 5. System at a Glance

### Component Map

```mermaid
graph TB
    subgraph User_Interfaces["User Interfaces"]
        TG["📱 Telegram<br/>(Any Chat)"]
        BROWSER["🌐 Web Browser<br/>(Admin Only)"]
    end

    subgraph Core_Services["Core Services (Docker)"]
        BOT["🤖 Bot Process<br/>src/bot.py"]
        ADMIN["🖥️ Admin Panel<br/>src/admin.py<br/>NiceGUI"]
        OLLAMA["🧠 Ollama<br/>qwen2.5:0.5b<br/>Local LLM"]
    end

    subgraph Data["Shared Data"]
        DB[("🗄️ SQLite<br/>WAL Mode")]
    end

    subgraph External["External Services"]
        LASTFM["🎵 Last.fm API 2.0"]
        SENTRY["🔍 Sentry<br/>(Error Tracking)"]
    end

    CADDY["🔒 Caddy<br/>HTTPS Proxy"]

    TG <-->|"Polling HTTPS"| BOT
    BROWSER -->|"HTTPS :443"| CADDY
    CADDY -->|"HTTP :8080"| ADMIN

    BOT -->|"pylast"| LASTFM
    BOT -->|"HTTP"| OLLAMA
    BOT <-->|"Read/Write"| DB
    ADMIN <-->|"Read/Write"| DB
    BOT -.->|"Errors"| SENTRY
```

### Data Model

```mermaid
erDiagram
    User {
        int id PK
        bigint telegram_id UK "Unique Telegram user ID"
        varchar telegram_username "Telegram @handle"
        varchar lastfm_username "Last.fm username"
    }

    Chat {
        int id PK
        bigint telegram_id UK "Unique Telegram chat ID"
        varchar telegram_chat_name "Chat title or username"
        varchar chat_type "private / group / supergroup / channel"
    }

    CommandLog {
        int id PK
        bigint user_id "Telegram user ID (not FK)"
        varchar username "Telegram @handle at time of command"
        varchar command "e.g. np, tops, vibe"
        varchar args "Command arguments string"
        int chat_id FK "References Chat"
        bigint timestamp "Unix epoch timestamp"
    }

    Chat ||--o{ CommandLog : "has"
```

---

## 6. AI Capabilities

All AI features run **100% locally** using [Ollama](https://ollama.com/) and the `qwen2.5:0.5b` model — a 400MB ultra-compact model chosen to operate within a 2GB RAM container.

```mermaid
graph LR
    subgraph AI_Pipeline["Local AI Pipeline"]
        INPUT["User's Listening Data<br/>(tracks / artists)"]
        PROMPT["Prompt Engineering<br/>(src/ai.py)"]
        OLLAMA["Ollama Server<br/>qwen2.5:0.5b"]
        OUTPUT["Generated Text Response"]
    end

    INPUT --> PROMPT
    PROMPT --> OLLAMA
    OLLAMA --> OUTPUT
```

### AI Feature Details

| Command | Input Data | Prompt Goal | Temperature | Max Tokens |
|---------|-----------|-------------|-------------|------------|
| `/vibe` | Last 10 scrobbles + current track | Mood/atmosphere description in 2-3 sentences with emojis | 0.8 | 100 |
| `/roast` | Top 10 artists + top 5 tracks (all-time) | Witty, humorous critique in 2-3 sentences | 0.9 | 120 |
| `/recommend` | Top 10 artists (all-time) | 5 lesser-known similar artists with brief rationale | 0.7 | 150 |

**Fallback behavior:** If Ollama is unreachable or model inference fails, all AI commands return a friendly error message rather than crashing.

**Model auto-provisioning:** On first AI command invocation, the bot automatically pulls `qwen2.5:0.5b` if it isn't already present in the Ollama volume.

---

## 7. Admin & Operations

The **NiceGUI Admin Dashboard** provides a web UI for monitoring and managing the bot's data.

### Admin Routes

| Route | Description |
|-------|-------------|
| `/login` | Credential-based login (username + password from env vars) |
| `/` | **Dashboard** — Total users, chats, commands, and today's activity |
| `/users` | **User management** — List all linked users, delete accounts |
| `/chats` | **Chat registry** — All known Telegram chats (private, group, channel) |
| `/logs` | **Command audit log** — Filterable history of all bot commands |

### Deployment Topology

```mermaid
graph TB
    subgraph VPS["VPS / Server"]
        subgraph Docker_Stack["Docker Compose Stack"]
            BOT_C["lastfmbucket-bot<br/>container"]
            ADMIN_C["lastfmbucket-admin<br/>container<br/>:8080"]
            OLLAMA_C["lastfmbucket-ollama<br/>container<br/>:11434<br/>2GB RAM limit"]
        end

        subgraph Caddy_Stack["Caddy Stack (External)"]
            CADDY_C["Caddy Container<br/>:443 → admin:8080"]
        end

        VOLUME[("./data volume<br/>SQLite DB")]
        OLLAMA_VOL[("ollama_data volume<br/>Model weights")]
    end

    INTERNET["🌐 Internet"]
    TELEGRAM_SRV["Telegram Servers"]

    INTERNET -->|"HTTPS :443"| CADDY_C
    CADDY_C -->|"navidrome-orchestra<br/>caddy-with-admin<br/>network"| ADMIN_C
    BOT_C -->|"Polling"| TELEGRAM_SRV
    BOT_C --- VOLUME
    ADMIN_C --- VOLUME
    BOT_C -->|"HTTP"| OLLAMA_C
    OLLAMA_C --- OLLAMA_VOL
```

### CI/CD Pipeline

```mermaid
flowchart LR
    PUSH["git push to main"] -->|"GitHub Actions trigger"| BUILD
    BUILD["Build Docker image"] --> PUSH_IMG
    PUSH_IMG["Push to Docker Hub"] --> DEPLOY
    DEPLOY["SSH into VPS"] --> PULL
    PULL["docker compose pull"] --> UP
    UP["docker compose up -d"]
```

---

## 8. Privacy & Data

- **What is stored:** Telegram user ID, Telegram @username, and Last.fm username. Command execution logs (command name, args, chat context, timestamp).
- **What is NOT stored:** Message content, passwords, audio data, or any media.
- **Data access:** Only accessible via the admin panel (password-protected) or direct database file access on the host.
- **Right to erasure:** Users can delete their own account data at any time via `/preferences` → Unlink account.
- **Last.fm data:** All Last.fm queries use public API endpoints and read-only consumer keys. No user authentication tokens are stored.

---

*For technical implementation details, see [ARCHITECTURE.md](../ARCHITECTURE.md).*  
*For the project overview and repository guide, see [README.md](../README.md).*
