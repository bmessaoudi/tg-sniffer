---
name: db-stats
description: "Show database statistics and message mapping info"
user-invocable: true
allowed-tools: [Bash, Read]
---

# Database Statistics

Query the SQLite database for statistics about message mappings.

## Database Location

File: `messages.db` in project root

## Queries to Run

Execute these SQL queries using sqlite3:

### 1. Total Mappings
```bash
sqlite3 messages.db "SELECT COUNT(*) as total FROM message_mappings;"
```

### 2. Mappings by Destination Channel
```bash
sqlite3 messages.db "SELECT destination_channel_id, COUNT(*) as count FROM message_mappings GROUP BY destination_channel_id ORDER BY count DESC;"
```

### 3. Mappings by Source Channel
```bash
sqlite3 messages.db "SELECT source_channel_id, COUNT(*) as count FROM message_mappings GROUP BY source_channel_id ORDER BY count DESC;"
```

### 4. Recent Activity (last 24h)
```bash
sqlite3 messages.db "SELECT COUNT(*) FROM message_mappings WHERE created_at > datetime('now', '-1 day');"
```

### 5. Oldest and Newest Mappings
```bash
sqlite3 messages.db "SELECT MIN(created_at) as oldest, MAX(created_at) as newest FROM message_mappings;"
```

### 6. Database Size
```bash
ls -lh messages.db
```

## Output Format

Present results in a clean summary:
- Total message mappings
- Breakdown by source/destination
- Recent activity metrics
- Database file size
- Estimated cleanup (messages older than 10 days)
