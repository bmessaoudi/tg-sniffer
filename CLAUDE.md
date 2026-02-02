# CLAUDE.md - tg-sniffer

## Project Overview

Telegram message forwarder that monitors source channels and copies messages to one or more destination channels. Supports message editing/deletion sync, reply chain tracking, and blocked word filtering.

**Repository**: https://github.com/bmessaoudi/tg-sniffer
**Main branch**: `main` | **Development**: `dev`

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Runtime | Python 3.9+ |
| Telegram API | Telethon 1.28.5 |
| Database | SQLite 3 (WAL mode) |
| Async | asyncio + aiosqlite |
| Config | python-dotenv |
| Container | Docker |

---

## Project Structure

```
tg-sniffer/
├── main.py              # Core bot application (entry point)
├── database.py          # Message mapping database module
├── generate_session.py  # Telegram auth helper (session string generation)
├── find_channel_id.py   # Channel discovery utility
├── requirements.txt     # Python dependencies
├── .env.example         # Configuration template
├── Dockerfile           # Container image
└── docker-compose.yml   # Container orchestration
```

### Key Modules

| File | Purpose | Key Lines |
|------|---------|-----------|
| `main.py` | Bot core, event handlers, queue system | 180-362 (queues), 468-653 (handlers) |
| `database.py` | MessageMapper class, schema, migrations | 14-289 |
| `generate_session.py` | Interactive Telegram login | 47-141 |

---

## Essential Commands

### Development
```bash
# Run the bot
python main.py

# Generate session string (interactive)
python generate_session.py

# Find channel IDs
python find_channel_id.py
```

### Docker
```bash
docker-compose up -d        # Start containerized
docker-compose logs -f      # View logs
docker-compose down         # Stop
```

### Dependencies
```bash
pip install -r requirements.txt
```

---

## Configuration

Required environment variables (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `API_ID` | Telegram API ID |
| `API_HASH` | Telegram API hash |
| `TELEGRAM_STRING_SESSION` | Auth session (from generate_session.py) |
| `SOURCE_CHANNELS` | Comma-separated source channel names/IDs |
| `DESTINATION_CHANNEL_IDS` | Comma-separated destination channel IDs |

Optional:
- `COPY_ENABLED` - Enable actual copying (default: false = dry-run)
- `BLOCKED_WORDS` - Comma-separated words to filter

Configuration validation: `main.py:113-134`

---

## Database Schema

**File**: `messages.db` (auto-created)

```sql
-- main.py:54-62
CREATE TABLE message_mappings (
    source_msg_id INTEGER NOT NULL,
    destination_msg_id INTEGER NOT NULL,
    source_channel_id INTEGER NOT NULL,
    destination_channel_id INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

Auto-migration support: `database.py:38-51`

---

## Event Handlers

| Event | Handler Location | Purpose |
|-------|-----------------|---------|
| NewMessage | `main.py:468-526` | Filter and forward new messages |
| MessageEdited | `main.py:532-580` | Sync edits to destinations |
| MessageDeleted | `main.py:583-653` | Sync deletions to destinations |

---

## Skills (Slash Commands)

| Command | Purpose |
|---------|---------|
| `/test-bot` | Test configuration in dry-run mode |
| `/add-channel` | Add source/destination channels |
| `/db-stats` | Show database statistics |
| `/check-config` | Validate environment setup |

---

## Agents (Specialized Assistants)

Use these agents via Task tool for domain-specific help:

| Agent | When to Use |
|-------|-------------|
| `telethon-expert` | Telegram API features, connection issues |
| `queue-analyzer` | Message delivery, throughput, retry logic |
| `database-reviewer` | Schema changes, query optimization |
| `feature-planner` | Planning new features |
| `debug-assistant` | Diagnosing bot issues |

---

## Additional Documentation

| Topic | File |
|-------|------|
| Design patterns & architecture | `.claude/docs/architectural_patterns.md` |
| Skills definitions | `.claude/skills/*/SKILL.md` |
| Agent definitions | `.claude/agents/*.md` |

---

## Quick Reference

- **Entry point**: `main.py` -> `main()` async function (`main.py:368`)
- **Queue system**: `MessageQueueManager` class (`main.py:295-362`)
- **Database access**: `MessageMapper` class (`database.py:14`)
- **Logging config**: `PrettyFormatter` (`main.py:17-70`)
- **Cleanup task**: 10-day retention (`main.py:435-446`)
