---
name: add-channel
description: "Add a new source or destination channel to the bot configuration"
user-invocable: true
allowed-tools: [Read, Edit, Bash]
---

# Add Channel

Help the user add a new source or destination channel.

## Arguments

`$ARGUMENTS` should specify:
- `source <channel_name_or_id>` - Add a source channel
- `destination <channel_id>` - Add a destination channel
- `find <search_term>` - Search for channel ID by name

## Workflow

### If finding a channel:
```bash
python find_channel_id.py
```
Then filter results for the search term.

### If adding a source channel:
1. Read current `.env` file
2. Parse existing SOURCE_CHANNELS value
3. Append new channel (comma-separated)
4. Update `.env` using Edit tool

### If adding a destination channel:
1. Read current `.env` file
2. Parse existing DESTINATION_CHANNEL_IDS value
3. Append new channel ID (comma-separated)
4. Update `.env` using Edit tool

## Validation

After modification:
1. Show the updated configuration
2. Remind user to restart the bot for changes to take effect
3. Suggest running `/test-bot` to verify

## Channel ID Format

- Source channels can be: `@username`, `channel_name`, or numeric ID
- Destination channels MUST be numeric IDs (negative for channels)
