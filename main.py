from telethon import TelegramClient, events
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("output.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
    
    logger.info("=" * 60)
    logger.info("TELEGRAM CHANNEL COPIER")
    logger.info("=" * 60)
    logger.info(f"Source channels configured: {source_channel_config}")
    logger.info(f"Destination channel ID: {destination_id}")
    logger.info("=" * 60)
    
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
                
                logger.info(f"New message from '{sender_chat.title}': {message.text[:100] if message.text else '[Media/No text]'}...")
                
                # Forward the message to destination
                await client.send_message(entity=destination_id, message=message)
                logger.info(f"✓ Message forwarded to destination channel")
                
            except Exception as e:
                logger.error(f"Error forwarding message: {e}")
        
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
