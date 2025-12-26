from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv
import logging
import sys
from datetime import datetime
import asyncio
from collections import deque
from database import MessageMapper

# =============================================================================
# PRETTY LOGGER CONFIGURATION
# =============================================================================

class PrettyFormatter(logging.Formatter):
    """Custom formatter with colors and better formatting."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',        # Green
        'WARNING': '\033[33m',     # Yellow
        'ERROR': '\033[31m',       # Red
        'CRITICAL': '\033[35m',    # Magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    def format(self, record):
        # Get color for this level
        color = self.COLORS.get(record.levelname, '')
        
        # Format timestamp
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Build the formatted message
        formatted = f"{self.DIM}{timestamp}{self.RESET} "
        formatted += f"{color}{self.BOLD}[{record.levelname}]{self.RESET} "
        formatted += f"{record.getMessage()}"
        
        return formatted


def setup_logger():
    """Setup logging with pretty console output and file logging."""
    logger = logging.getLogger('tg-sniffer')
    logger.setLevel(logging.INFO)
    
    # File handler (detailed, no colors)
    file_handler = logging.FileHandler('output.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s'
    ))
    
    # Console handler (pretty, with colors)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(PrettyFormatter())
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


logger = setup_logger()

# Load environment variables
load_dotenv()

# =============================================================================
# CONFIGURATION - All settings loaded from environment variables
# =============================================================================

# Telegram API credentials (required)
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
TELEGRAM_STRING_SESSION = os.getenv('TELEGRAM_STRING_SESSION')

# Source channels - comma-separated list of channel names OR IDs
# Example: "Channel Name 1,Channel Name 2" or "1234567890,0987654321"
SOURCE_CHANNELS = os.getenv('SOURCE_CHANNELS', '')

# Destination channel ID (required)
DESTINATION_CHANNEL_ID = os.getenv('DESTINATION_CHANNEL_ID')

# =============================================================================
# COPY CONTROL - Enable/disable actual message copying
# =============================================================================
# Set to 'true' to enable copying, 'false' for dry-run mode (just logging)
COPY_ENABLED = os.getenv('COPY_ENABLED', 'false').lower() == 'true'

# =============================================================================
# BLOCKED WORDS - Messages containing these words will NOT be copied
# =============================================================================
# Comma-separated list of words/phrases that block message copying
# Example: "zoom.us,meet.google.com,teams.microsoft.com"
BLOCKED_WORDS_RAW = os.getenv('BLOCKED_WORDS', '')
BLOCKED_WORDS = [word.strip().lower() for word in BLOCKED_WORDS_RAW.split(',') if word.strip()]

# =============================================================================
# VALIDATION
# =============================================================================

def validate_config():
    """Validate that all required configuration is present."""
    errors = []
    
    if not API_ID:
        errors.append("API_ID is required")
    if not API_HASH:
        errors.append("API_HASH is required")
    if not TELEGRAM_STRING_SESSION:
        errors.append("TELEGRAM_STRING_SESSION is required")
    if not SOURCE_CHANNELS:
        errors.append("SOURCE_CHANNELS is required")
    if not DESTINATION_CHANNEL_ID:
        errors.append("DESTINATION_CHANNEL_ID is required")
    
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        logger.error("Please check your .env file and ensure all required variables are set.")
        sys.exit(1)
    
    logger.info("Configuration validated successfully")


def parse_source_channels():
    """Parse SOURCE_CHANNELS into a list of names and/or IDs."""
    channels = []
    for channel in SOURCE_CHANNELS.split(','):
        channel = channel.strip()
        if channel:
            # Try to parse as integer (channel ID), otherwise treat as name
            try:
                channels.append(int(channel))
            except ValueError:
                channels.append(channel)
    return channels


# =============================================================================
# MESSAGE QUEUE SYSTEM - Ensures chronological order and no message loss
# =============================================================================

class MessageQueue:
    """Thread-safe async message queue with retry support."""
    
    def __init__(self, max_retries=5, retry_delay=2.0):
        self.queue = asyncio.Queue()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.failed_messages = deque(maxlen=100)  # Keep track of failed messages
        self.stats = {
            'total_received': 0,
            'total_sent': 0,
            'total_blocked': 0,
            'total_failed': 0,
            'total_edited': 0,
            'total_deleted': 0,
        }
        self._worker_task = None
        self._client = None
        self._destination_id = None
        self._message_mapper = None
    
    def set_client(self, client, destination_id, message_mapper=None):
        """Set the Telegram client, destination, and message mapper."""
        self._client = client
        self._destination_id = destination_id
        self._message_mapper = message_mapper
    
    async def add_message(self, message, sender_title, preview, source_channel_id, reply_to_dest_id=None):
        """Add a message to the queue."""
        self.stats['total_received'] += 1
        await self.queue.put({
            'message': message,
            'sender_title': sender_title,
            'preview': preview,
            'source_channel_id': source_channel_id,
            'reply_to_dest_id': reply_to_dest_id,
            'timestamp': datetime.now(),
            'retries': 0,
        })
        queue_size = self.queue.qsize()
        if queue_size > 1:
            logger.info(f"   📥 Queued (position: {queue_size})")
    
    async def start_worker(self):
        """Start the queue worker."""
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("📋 Message queue worker started")
    
    async def stop_worker(self):
        """Stop the queue worker gracefully."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("📋 Message queue worker stopped")
            self._log_stats()
    
    def _log_stats(self):
        """Log final statistics."""
        logger.info("")
        logger.info("╔" + "═" * 58 + "╗")
        logger.info("║" + "  📊 SESSION STATISTICS".ljust(58) + "║")
        logger.info("╠" + "═" * 58 + "╣")
        logger.info("║" + f"  Messages received: {self.stats['total_received']}".ljust(58) + "║")
        logger.info("║" + f"  Messages sent: {self.stats['total_sent']}".ljust(58) + "║")
        logger.info("║" + f"  Messages edited: {self.stats['total_edited']}".ljust(58) + "║")
        logger.info("║" + f"  Messages deleted: {self.stats['total_deleted']}".ljust(58) + "║")
        logger.info("║" + f"  Messages blocked: {self.stats['total_blocked']}".ljust(58) + "║")
        logger.info("║" + f"  Messages failed: {self.stats['total_failed']}".ljust(58) + "║")
        logger.info("╚" + "═" * 58 + "╝")
    
    async def _process_queue(self):
        """Process messages from the queue one by one (in order)."""
        while True:
            try:
                # Wait for a message
                item = await self.queue.get()
                
                message = item['message']
                source_channel_id = item['source_channel_id']
                sender_title = item['sender_title']
                preview = item['preview']
                reply_to_dest_id = item.get('reply_to_dest_id')
                retries = item['retries']
                
                success = False
                
                while not success and retries < self.max_retries:
                    try:
                        # Send the message (with reply_to if applicable)
                        sent_message = await self._client.send_message(
                            entity=self._destination_id,
                            message=message,
                            reply_to=reply_to_dest_id
                        )
                        success = True
                        self.stats['total_sent'] += 1
                        
                        # Save mapping to database
                        if self._message_mapper and sent_message:
                            await self._message_mapper.add_mapping(
                                source_msg_id=message.id,
                                destination_msg_id=sent_message.id,
                                source_channel_id=source_channel_id
                            )
                        
                        logger.info(f"   ✅ COPIED to destination")
                        logger.info(f"{'─' * 50}")
                        
                    except Exception as e:
                        retries += 1
                        if retries < self.max_retries:
                            logger.warning(f"   ⚠️  Retry {retries}/{self.max_retries} - Error: {e}")
                            await asyncio.sleep(self.retry_delay * retries)  # Exponential backoff
                        else:
                            logger.error(f"   ❌ FAILED after {self.max_retries} retries: {e}")
                            self.stats['total_failed'] += 1
                            self.failed_messages.append({
                                'preview': preview,
                                'sender': sender_title,
                                'error': str(e),
                                'timestamp': item['timestamp'],
                            })
                
                self.queue.task_done()
                
            except asyncio.CancelledError:
                # Worker is being stopped, process remaining messages
                remaining = self.queue.qsize()
                if remaining > 0:
                    logger.warning(f"⚠️  {remaining} messages still in queue!")
                raise


# Global message queue instance
message_queue = MessageQueue(max_retries=5, retry_delay=2.0)


# =============================================================================
# MAIN BOT LOGIC
# =============================================================================

async def main():
    """Main bot function."""
    validate_config()
    
    source_channel_config = parse_source_channels()
    destination_id = int(DESTINATION_CHANNEL_ID)
    
    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + "  📡 TELEGRAM CHANNEL COPIER".ljust(58) + "║")
    logger.info("╠" + "═" * 58 + "╣")
    logger.info("║" + f"  Source: {source_channel_config}"[:57].ljust(58) + "║")
    logger.info("║" + f"  Destination: {destination_id}".ljust(58) + "║")
    logger.info("╠" + "═" * 58 + "╣")
    
    # Show copy status
    if COPY_ENABLED:
        logger.info("║" + "  ✅ COPY MODE: ENABLED (messages will be copied)".ljust(58) + "║")
    else:
        logger.info("║" + "  ⏸️  COPY MODE: DISABLED (dry-run, just logging)".ljust(58) + "║")
    
    # Show blocked words
    if BLOCKED_WORDS:
        logger.info("║" + f"  🚫 Blocked words: {', '.join(BLOCKED_WORDS[:3])}{'...' if len(BLOCKED_WORDS) > 3 else ''}".ljust(58) + "║")
    else:
        logger.info("║" + "  🚫 Blocked words: (none configured)".ljust(58) + "║")
    
    # Show queue info
    logger.info("╠" + "═" * 58 + "╣")
    logger.info("║" + "  📋 MESSAGE QUEUE: ENABLED (ordered delivery)".ljust(58) + "║")
    logger.info("║" + f"  🔄 Max retries: {message_queue.max_retries}".ljust(58) + "║")
    
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")
    
    # Initialize client
    client = TelegramClient(
        StringSession(TELEGRAM_STRING_SESSION),
        API_ID,
        API_HASH
    )
    
    try:
        await client.start()
        logger.info("Client connected successfully")
        
        # Initialize message mapper (database)
        message_mapper = MessageMapper('messages.db')
        await message_mapper.init_db()
        
        # Run initial cleanup
        await message_mapper.cleanup_old(days=10)
        
        # Setup message queue with database
        message_queue.set_client(client, destination_id, message_mapper)
        await message_queue.start_worker()
        
        # Start daily cleanup task
        async def daily_cleanup():
            """Run cleanup every 24 hours."""
            while True:
                await asyncio.sleep(86400)  # 24 hours
                try:
                    deleted_count = await message_mapper.cleanup_old(days=10)
                    if deleted_count > 0:
                        logger.info(f"🧹 Daily cleanup completed: {deleted_count} old mappings removed")
                except Exception as e:
                    logger.error(f"❌ Daily cleanup failed: {e}")
        
        cleanup_task = asyncio.create_task(daily_cleanup())
        
        # Find matching source channels
        matched_channel_ids = []
        
        async for dialog in client.iter_dialogs():
            channel_id = dialog.entity.id
            channel_name = dialog.name
            
            # Match by ID or by name
            if channel_id in source_channel_config or channel_name in source_channel_config:
                logger.info(f"✓ Matched source channel: '{channel_name}' (ID: {channel_id})")
                matched_channel_ids.append(channel_id)
        
        if not matched_channel_ids:
            logger.error("No source channels found! Please check your SOURCE_CHANNELS configuration.")
            logger.error("Make sure the account is a member of the specified channels.")
            sys.exit(1)
        
        logger.info(f"Monitoring {len(matched_channel_ids)} channel(s)")
        
        # Register message handler
        @client.on(events.NewMessage(chats=matched_channel_ids))
        async def message_handler(event):
            try:
                message = event.message
                sender_chat = await event.get_chat()
                
                # Get message preview (first 50 chars)
                text = message.text or ''
                preview = text[:50].replace('\n', ' ') if text else '[Media/No text]'
                if len(text) > 50:
                    preview += '...'
                
                # Pretty log the incoming message
                logger.info(f"{'─' * 50}")
                logger.info(f"📨 NEW MESSAGE")
                logger.info(f"   From: {sender_chat.title}")
                logger.info(f"   Preview: {preview}")
                
                # Check for blocked words
                if BLOCKED_WORDS:
                    message_lower = text.lower()
                    for blocked_word in BLOCKED_WORDS:
                        if blocked_word in message_lower:
                            logger.warning(f"   ⛔ BLOCKED - Contains: '{blocked_word}'")
                            logger.info(f"{'─' * 50}")
                            message_queue.stats['total_blocked'] += 1
                            return
                
                # Check if copy is enabled
                if not COPY_ENABLED:
                    logger.info(f"   ⏸️  DRY-RUN MODE - Message NOT copied")
                    logger.info(f"{'─' * 50}")
                    return
                
                # Check if this message is a reply to another message
                reply_to_dest_id = None
                if message.reply_to_msg_id:
                    # Look up the destination message ID for the replied message
                    reply_to_dest_id = await message_mapper.get_destination_id(
                        source_msg_id=message.reply_to_msg_id,
                        source_channel_id=sender_chat.id
                    )
                    if reply_to_dest_id:
                        logger.info(f"   ↩️  Reply to message #{message.reply_to_msg_id} → #{reply_to_dest_id}")
                    else:
                        logger.info(f"   ↩️  Reply to message #{message.reply_to_msg_id} (original not found)")
                
                # Add message to queue for ordered processing
                await message_queue.add_message(
                    message=message,
                    sender_title=sender_chat.title,
                    preview=preview,
                    source_channel_id=sender_chat.id,
                    reply_to_dest_id=reply_to_dest_id
                )
                
            except Exception as e:
                logger.error(f"❌ Error processing message: {e}")
        
        # Register message edit handler
        @client.on(events.MessageEdited(chats=matched_channel_ids))
        async def edit_handler(event):
            """Handle message edits in source channels."""
            try:
                if not COPY_ENABLED:
                    return
                
                message = event.message
                sender_chat = await event.get_chat()
                
                # Get destination message ID from database
                destination_msg_id = await message_mapper.get_destination_id(
                    source_msg_id=message.id,
                    source_channel_id=sender_chat.id
                )
                
                if not destination_msg_id:
                    logger.debug(f"No mapping found for edited message {message.id}")
                    return
                
                # Get message preview
                text = message.text or ''
                preview = text[:50].replace('\n', ' ') if text else '[Media/No text]'
                if len(text) > 50:
                    preview += '...'
                
                # Edit the message in destination
                await client.edit_message(
                    entity=destination_id,
                    message=destination_msg_id,
                    text=message.text
                )
                
                message_queue.stats['total_edited'] += 1
                logger.info(f"{'─' * 50}")
                logger.info(f"✏️  MESSAGE EDITED")
                logger.info(f"   From: {sender_chat.title}")
                logger.info(f"   Preview: {preview}")
                logger.info(f"   ✅ EDIT synced to destination")
                logger.info(f"{'─' * 50}")
                
            except Exception as e:
                logger.error(f"❌ Error handling message edit: {e}")
        
        # Register message delete handler
        @client.on(events.MessageDeleted())
        async def delete_handler(event):
            """Handle message deletions in source channels."""
            try:
                if not COPY_ENABLED:
                    return
                
                # Get deleted message IDs
                deleted_ids = event.deleted_ids
                
                # Check if we have a channel_id (needed for our mappings)
                # For channel messages, we can get the channel_id
                channel_id = None
                if hasattr(event, 'chat_id') and event.chat_id:
                    channel_id = event.chat_id
                elif hasattr(event, 'peer_id') and event.peer_id:
                    try:
                        channel_id = event.peer_id.channel_id
                    except AttributeError:
                        pass
                
                if not channel_id:
                    # Try to find mappings for any of our monitored channels
                    for source_channel_id in matched_channel_ids:
                        dest_ids = await message_mapper.get_destination_ids(
                            source_msg_ids=deleted_ids,
                            source_channel_id=source_channel_id
                        )
                        if dest_ids:
                            channel_id = source_channel_id
                            break
                
                if not channel_id or channel_id not in matched_channel_ids:
                    return
                
                # Get destination message IDs from database
                destination_msg_ids = await message_mapper.get_destination_ids(
                    source_msg_ids=deleted_ids,
                    source_channel_id=channel_id
                )
                
                if not destination_msg_ids:
                    return
                
                # Delete messages in destination
                for dest_id in destination_msg_ids:
                    try:
                        await client.delete_messages(
                            entity=destination_id,
                            message_ids=[dest_id]
                        )
                        message_queue.stats['total_deleted'] += 1
                    except Exception as e:
                        logger.error(f"❌ Failed to delete message {dest_id}: {e}")
                
                # Remove mappings from database
                await message_mapper.delete_mappings(
                    source_msg_ids=deleted_ids,
                    source_channel_id=channel_id
                )
                
                logger.info(f"{'─' * 50}")
                logger.info(f"🗑️  MESSAGE(S) DELETED")
                logger.info(f"   Count: {len(destination_msg_ids)}")
                logger.info(f"   ✅ DELETE synced to destination")
                logger.info(f"{'─' * 50}")
                
            except Exception as e:
                logger.error(f"❌ Error handling message deletion: {e}")
        
        logger.info("=" * 60)
        logger.info("Bot is now running and listening for messages...")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)
        
        await client.run_until_disconnected()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        # Cancel cleanup task
        if 'cleanup_task' in locals():
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
        
        await message_queue.stop_worker()
        
        # Close database
        if 'message_mapper' in locals():
            await message_mapper.close()
        
        await client.disconnect()
        logger.info("Client disconnected")


if __name__ == "__main__":
    asyncio.run(main())
