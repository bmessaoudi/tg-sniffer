from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv
import logging
import sys
from datetime import datetime

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
                            return
                
                # Check if copy is enabled
                if not COPY_ENABLED:
                    logger.info(f"   ⏸️  DRY-RUN MODE - Message NOT copied")
                    logger.info(f"{'─' * 50}")
                    return
                
                # Forward the message to destination
                await client.send_message(entity=destination_id, message=message)
                logger.info(f"   ✅ COPIED to destination")
                logger.info(f"{'─' * 50}")
                
            except Exception as e:
                logger.error(f"❌ Error forwarding message: {e}")
        
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
        await client.disconnect()
        logger.info("Client disconnected")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
