---
name: test-bot
description: "Test the bot configuration in dry-run mode to verify channels and settings"
user-invocable: true
allowed-tools: [Bash, Read, Grep]
---

# Test Bot Configuration

Run the bot in dry-run mode to verify configuration without actually forwarding messages.

## Pre-flight Checks

1. **Verify .env exists and has required variables**:
   - Read `.env` file
   - Check for: API_ID, API_HASH, TELEGRAM_STRING_SESSION, SOURCE_CHANNELS, DESTINATION_CHANNEL_IDS

2. **Ensure COPY_ENABLED is false** (dry-run mode):
   - If COPY_ENABLED=true, warn the user before proceeding

3. **Check dependencies**:
   ```bash
   pip list | grep -E "telethon|python-dotenv|aiosqlite"
   ```

## Test Execution

Run with timeout to capture initial connection and channel resolution:
```bash
timeout 30 python main.py || true
```

## Expected Output Analysis

Look for these indicators in the output:
- "Connected successfully" or similar connection message
- Source channels being resolved
- Any configuration errors or warnings
- Rate limit warnings

## Report

Provide a summary:
1. Configuration status (complete/incomplete)
2. Connection status
3. Channels found vs configured
4. Any errors or warnings detected
