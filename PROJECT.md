# Project: lastfmbucket-bot Documentation & Agent Readiness

> 📘 See also: [README.md](README.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/PRODUCT_PRESENTATION.md](docs/PRODUCT_PRESENTATION.md)

## Architecture & Subsystems
`lastfmbucket-bot` is a dual-process Python application (`bot` and `admin`) with an auxiliary `ollama` container, sharing an SQLite database:
1. **Telegram Bot Engine (`src/bot.py`, `src/commands.py`, `src/callbacks.py`, `src/services.py`)**:
   - `python-telegram-bot` v22.8 running in polling mode.
   - 14 slash commands: `/start`, `/status`, `/np`, `/tops`, `/collage`, `/preferences`, `/help`, `/changelog`, `/set`, `/privacy`, `/compare`, `/vibe`, `/roast`, `/recommend`.
   - Callback queries with strict 64-byte compact protocol: `v|action|owner_id|entity|period|size`.
   - Visual composite image grid generator powered by `lastfmcollagegenerator` v1.3.0 (async pipeline, WebP export, themes, filters).
2. **Database & Data Layer (`src/db.py`)**:
   - Peewee ORM 3.18.3 with SQLite in WAL mode.
   - Models: `User`, `Chat`, `CommandLog`.
3. **External API & LLM Integrations (`src/lastfm.py`, `src/ai.py`)**:
   - `pylast` 7.0.0 for Last.fm API (tracks, top artists/albums, user info).
   - `ollama` client with `qwen2.5:0.5b` for music taste roasts, vibe summaries, and recommendations.
4. **NiceGUI Admin Web UI (`src/admin.py`)**:
   - NiceGUI 2.x admin panel with 5 routes: `/login`, `/` (dashboard), `/users`, `/chats`, `/logs`.
5. **Tooling & Deployment (`pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `deploy.sh`)**:
   - Python >=3.14 with `uv` package manager and `ruff` linter.
   - Containerized multi-service deployment behind Caddy reverse proxy.

## Feature Inventory
| # | Feature / Artifact | Description | Milestone | Source | Status |
|---|--------------------|-------------|-----------|--------|---------|
| 1 | Master Architecture Doc (`ARCHITECTURE.md`) | Comprehensive architecture, subsystems, data flow, component breakdown, database schema, and deployment architecture. Updated with Mermaid diagrams and cross-references | M1 | Survey (Explorers 1, 2, Spec Miner 1) + M4 | DONE |
| 2 | Agent Context Document (`CONTEXT.md`) | Single-stop quickstart context for incoming agents: bot commands, database models, NiceGUI UI, API matrix, LLM prompt engineering, and operational runbook | M1 | Survey (Explorers 1, 2, Spec Miner 1) | DONE |
| 3 | Limitations & Gap Analysis | Complete catalog of 8+ identified bugs, concurrency bottlenecks (event loop blocking), schema drift, missing error handlers, and technical debt | M1 | Survey (Explorers 1, 2, Spec Miner 1) | DONE |
| 4 | Agent Ignore Rules (`.agignore`) | Ignore patterns for SQLite databases, virtual environments, caches, logs, and artifacts to optimize agent context windows | M2 | Survey (Explorer 2) | DONE |
| 5 | Agent Operational Skill (`SKILL.md`) | Structured skill guide with exact shell commands for `uv`, `pytest`, `ruff`, Docker run, database queries, and development workflows | M2 | Survey (Explorer 2) | DONE |
| 6 | Quality & Integrity Verification | Multi-agent review (x2), adversarial challenge (x2), and forensic audit (x1) of all generated documentation and agent readiness artifacts | M3 | Project Pattern Gate | DONE (VERIFIED) |
| 7 | Repository README (`README.md`) | Complete, professional repository entry point with badges, feature table, architecture overview, quickstart guide, command cheatsheet, configuration reference, and cross-links | M4 | Documentation Sprint | DONE |
| 8 | Product Presentation (`docs/PRODUCT_PRESENTATION.md`) | High-level product overview and stakeholder presentation: value proposition, feature showcase, user journeys, AI capabilities, deployment topology, and privacy policy — with Mermaid diagrams | M4 | Documentation Sprint | DONE |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Architecture & Context Documentation | Author `ARCHITECTURE.md` and `CONTEXT.md` with complete subsystem maps, schema references, and gap analysis | Survey Done | DONE |
| 2 | Agent Readiness & Operational Skill | Author `.agignore` and `SKILL.md` (and `.gemini/skills/lastfmbucket-skill/SKILL.md`) | M1 | DONE |
| 3 | Independent Verification & Audit | 2 Reviewers, 2 Challengers, and 1 Forensic Auditor gate check | M1, M2 | DONE |
| 4 | Public & Product Documentation | Author `README.md`, `docs/PRODUCT_PRESENTATION.md`, and upgrade `ARCHITECTURE.md` with Mermaid diagrams | M1, M2, M3 | DONE |

## Code Layout & File Ownership
- `/Users/priera/dev/workspace/lastfmbucket-bot/README.md` (Repository Entry Point & Quickstart Guide)
- `/Users/priera/dev/workspace/lastfmbucket-bot/ARCHITECTURE.md` (Master Architecture & Gap Analysis — includes Mermaid diagrams)
- `/Users/priera/dev/workspace/lastfmbucket-bot/docs/PRODUCT_PRESENTATION.md` (Product Overview & Stakeholder Presentation)
- `/Users/priera/dev/workspace/lastfmbucket-bot/CONTEXT.md` (Agent Fast-Onboarding Context)
- `/Users/priera/dev/workspace/lastfmbucket-bot/.agignore` (Agent Ignore Patterns)
- `/Users/priera/dev/workspace/lastfmbucket-bot/SKILL.md` (Operational Repository Skill)
- `/Users/priera/dev/workspace/lastfmbucket-bot/.gemini/skills/lastfmbucket-skill/SKILL.md` (Gemini Standard Skill)
- `/Users/priera/dev/workspace/lastfmbucket-bot/PROJECT.md` (Project Scope & Status)
- `/Users/priera/dev/workspace/lastfmbucket-bot/.agents/*` (Agent metadata & reports)
