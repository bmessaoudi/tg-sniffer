# Architectural Patterns

## Overview

This document describes the architectural patterns and design decisions used throughout the tg-sniffer codebase.

---

## 1. Async Queue Pattern

**Purpose**: Reliable message delivery with ordered processing per destination.

**Implementation**: `MessageQueueManager` + `DestinationQueue` classes

**Locations**:
- `main.py:180-293` - DestinationQueue implementation
- `main.py:295-362` - MessageQueueManager orchestration

**Key characteristics**:
- One queue per destination channel (1:1 isolation)
- `asyncio.Queue` for thread-safe async operations
- Worker coroutine per queue for continuous processing
- Broadcast method for one-to-many distribution

**Usage**:
```python
queue_manager = MessageQueueManager(mapper, destinations)
await queue_manager.start_workers()
await queue_manager.broadcast(message, source_channel_id, reply_to_id)
```

---

## 2. Retry with Exponential Backoff

**Purpose**: Handle transient failures (rate limits, network issues) gracefully.

**Implementation**: `DestinationQueue._send_message()` method

**Location**: `main.py:224-266`

**Parameters**:
- Max retries: 5
- Backoff: `2 * attempt` seconds
- Logs each retry attempt

**Pattern**:
```python
for attempt in range(1, max_retries + 1):
    try:
        # operation
        return result
    except Exception:
        if attempt == max_retries:
            raise
        await asyncio.sleep(2 * attempt)
```

---

## 3. Repository Pattern (Database Access)

**Purpose**: Encapsulate database operations behind a clean async API.

**Implementation**: `MessageMapper` class

**Location**: `database.py:14-289`

**Characteristics**:
- Async context manager support
- Connection pooling via single shared connection
- WAL mode for concurrent reads (`database.py:36`)
- All methods are async (`async def`)

**Core operations**:
| Method | Line | Purpose |
|--------|------|---------|
| `add_mapping()` | 86 | Store source-to-destination mapping |
| `get_destination_id()` | 105 | Single lookup |
| `get_all_destination_mappings()` | 127 | Multi-destination lookup |
| `cleanup_old()` | 166 | TTL-based cleanup |

---

## 4. Event-Driven Architecture

**Purpose**: React to Telegram events (new messages, edits, deletions).

**Implementation**: Telethon event handlers with decorators

**Locations**:
- `main.py:468-526` - NewMessage handler
- `main.py:532-580` - MessageEdited handler
- `main.py:583-653` - MessageDeleted handler

**Pattern**:
```python
@client.on(events.NewMessage(chats=source_ids))
async def handler(event):
    # process event
```

**Event flow**:
1. Event received from Telegram
2. Filter/validate (blocked words, source check)
3. Queue for async processing or immediate action
4. Update database mappings

---

## 5. Configuration Validation Pattern

**Purpose**: Fail fast with clear error messages on missing/invalid config.

**Implementation**: Centralized validation at startup

**Locations**:
- `main.py:72-108` - Environment variable loading
- `main.py:113-134` - Validation with descriptive errors

**Characteristics**:
- All required vars checked before any operation
- Type conversion (str to int) with error handling
- Default values for optional parameters
- Early exit on validation failure

---

## 6. Auto-Migration Pattern

**Purpose**: Evolve database schema without manual intervention.

**Implementation**: Column detection + ALTER TABLE

**Location**: `database.py:38-51`

**Pattern**:
```python
# Check existing columns
cursor = await conn.execute("PRAGMA table_info(table_name)")
columns = {row[1] for row in await cursor.fetchall()}

# Migrate if needed
if 'new_column' not in columns:
    await conn.execute("ALTER TABLE ... ADD COLUMN ...")
```

---

## 7. Graceful Shutdown Pattern

**Purpose**: Clean resource release and final statistics on exit.

**Implementation**: Try-finally with cleanup sequence

**Locations**:
- `main.py:655-687` - Main function cleanup
- `main.py:313-328` - Queue manager shutdown

**Shutdown sequence**:
1. Stop all worker coroutines
2. Wait for queue drain
3. Print statistics
4. Close database connection
5. Disconnect Telegram client

---

## 8. Dual-Output Logging

**Purpose**: Colorized console output + plain file logging.

**Implementation**: Custom `PrettyFormatter` with ANSI codes

**Location**: `main.py:17-70`

**Configuration**:
- Console: Colorized with level-specific prefixes
- File: Plain text to `output.log`
- Both handlers attached to root logger

---

## 9. Reply Chain Tracking

**Purpose**: Maintain reply relationships across channel forwarding.

**Implementation**: Database lookup before forwarding

**Location**: `main.py:503-516`

**Flow**:
1. Check if original message has `reply_to_msg_id`
2. Query database for destination mapping of replied message
3. Forward with `reply_to` parameter pointing to destination message ID
4. Store new mapping including reply context

---

## Common Anti-Patterns Avoided

1. **No global state** - All state encapsulated in classes
2. **No synchronous blocking** - Full async/await usage
3. **No hardcoded values** - Configuration via environment
4. **No silent failures** - All errors logged with context
