---
name: check-config
description: "Validate bot configuration and environment setup"
user-invocable: true
allowed-tools: [Read, Bash, Glob]
---

# Check Configuration

Validate the bot's configuration without running it.

## Checks to Perform

### 1. Environment File
- Verify `.env` exists
- Compare against `.env.example` for missing variables
- Check for empty required values

### 2. Required Variables
| Variable | Validation |
|----------|------------|
| API_ID | Must be numeric |
| API_HASH | Must be 32 hex characters |
| TELEGRAM_STRING_SESSION | Must be non-empty base64-like string |
| SOURCE_CHANNELS | Must be comma-separated list |
| DESTINATION_CHANNEL_IDS | Must be comma-separated numeric IDs |

### 3. Optional Variables
- COPY_ENABLED: Should be 'true' or 'false'
- BLOCKED_WORDS: Comma-separated, no validation needed

### 4. Dependencies
```bash
pip list 2>/dev/null | grep -E "telethon|python-dotenv|aiosqlite" || echo "Check pip installation"
```

### 5. Database State
- Check if `messages.db` exists
- If exists, verify it's a valid SQLite database:
  ```bash
  sqlite3 messages.db "SELECT name FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "No database yet"
  ```

### 6. Docker Configuration (if using)
- Check Dockerfile exists
- Check docker-compose.yml exists

## Output

Generate a configuration report:
- Status for each check
- Warnings for potential issues
- Suggestions for fixes
