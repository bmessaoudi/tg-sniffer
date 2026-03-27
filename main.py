from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ChannelPrivateError, UserNotParticipantError, ChatWriteForbiddenError, MessageNotModifiedError
from telethon.tl.types import DocumentAttributeFilename, DocumentAttributeAudio, DocumentAttributeVideo, DocumentAttributeImageSize, DocumentAttributeAnimated, DocumentAttributeSticker

# Monkey-patch Telethon's NO_UPDATES_TIMEOUT from 15 min to 60 seconds.
# Telegram doesn't push real-time updates for some supergroups/forum topics,
# so Telethon falls back to polling via getChannelDifference every NO_UPDATES_TIMEOUT.
# See: https://github.com/LonamiWebs/Telethon/issues/4345
import telethon._updates.messagebox as _mb
_mb.NO_UPDATES_TIMEOUT = 60

import os
from dotenv import load_dotenv
import logging
import sys
from datetime import datetime
import asyncio
import time
from collections import deque
from dataclasses import dataclass
from database import MessageMapper
from typing import List, Dict, Optional, Union

@dataclass
class Route:
    """A routing rule: source channel -> list of destination channels, with optional topic filter."""
    source: Union[int, str]      # Channel ID or name
    destinations: List[int]      # Destination channel IDs
    topic_id: Optional[int]      # None = all messages, int = only that forum topic
    copy_media: bool = False     # True = forward media, False = text-only


@dataclass
class ResolvedRoute:
    """A route with the source resolved to a numeric channel ID."""
    source_channel_id: int
    destinations: List[int]
    topic_id: Optional[int]
    copy_media: bool = False


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
SESSION_FILE = os.getenv('SESSION_FILE', 'tg-sniffer')

# Source channels - comma-separated list of channel names OR IDs
# Example: "Channel Name 1,Channel Name 2" or "1234567890,0987654321"
SOURCE_CHANNELS = os.getenv('SOURCE_CHANNELS', '')

# Destination channel IDs - comma-separated list of channel IDs
# Example: "1234567890,0987654321"
DESTINATION_CHANNEL_IDS = os.getenv('DESTINATION_CHANNEL_IDS', '')

# Per-source routing (advanced, overrides SOURCE_CHANNELS + DESTINATION_CHANNEL_IDS)
# Format: source->dest1,dest2;source2/topic_id->dest3
CHANNEL_ROUTES = os.getenv('CHANNEL_ROUTES', '')

# Legacy support: single destination channel
DESTINATION_CHANNEL_ID = os.getenv('DESTINATION_CHANNEL_ID', '')

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
    if not TELEGRAM_STRING_SESSION and not os.path.exists(f'{SESSION_FILE}.session'):
        errors.append("TELEGRAM_STRING_SESSION is required (or provide an existing SESSION_FILE)")

    # CHANNEL_ROUTES replaces SOURCE_CHANNELS + DESTINATION_CHANNEL_IDS
    if not CHANNEL_ROUTES:
        if not SOURCE_CHANNELS:
            errors.append("SOURCE_CHANNELS is required (or use CHANNEL_ROUTES)")
        if not DESTINATION_CHANNEL_IDS and not DESTINATION_CHANNEL_ID:
            errors.append("DESTINATION_CHANNEL_IDS is required (or use CHANNEL_ROUTES)")
    
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


def parse_destination_channels() -> List[int]:
    """Parse DESTINATION_CHANNEL_IDS into a list of IDs."""
    channels = []
    
    # First try new format (comma-separated list)
    if DESTINATION_CHANNEL_IDS:
        for channel in DESTINATION_CHANNEL_IDS.split(','):
            channel = channel.strip()
            if channel:
                try:
                    channels.append(int(channel))
                except ValueError:
                    logger.warning(f"Invalid destination channel ID (must be numeric): {channel}")
    
    # Fallback to legacy single destination
    if not channels and DESTINATION_CHANNEL_ID:
        try:
            channels.append(int(DESTINATION_CHANNEL_ID))
            logger.info("Using legacy DESTINATION_CHANNEL_ID format")
        except ValueError:
            logger.error(f"Invalid DESTINATION_CHANNEL_ID: {DESTINATION_CHANNEL_ID}")
    
    return channels


def _parse_channel_routes(raw: str) -> List[Route]:
    """Parse CHANNEL_ROUTES format: source->dest1,dest2;source/topic->dest3"""
    routes = []
    for rule in raw.split(';'):
        rule = rule.strip()
        if not rule:
            continue

        if '->' not in rule:
            logger.warning(f"Invalid route (missing '->'): {rule}")
            continue

        source_part, dest_part = rule.split('->', 1)
        source_part = source_part.strip()
        dest_part = dest_part.strip()

        if not source_part or not dest_part:
            logger.warning(f"Invalid route (empty source or destinations): {rule}")
            continue

        # Parse +media flag
        copy_media = False
        if '+media' in source_part:
            copy_media = True
            source_part = source_part.replace('+media', '')

        # Parse topic filter: source_id/topic_id
        topic_id = None
        if '/' in source_part:
            source_str, topic_str = source_part.rsplit('/', 1)
            try:
                topic_id = int(topic_str)
                source_part = source_str
            except ValueError:
                logger.warning(f"Invalid topic ID '{topic_str}' in route: {rule}")
                continue

        # Parse source (int or string name)
        try:
            source: Union[int, str] = int(source_part)
        except ValueError:
            source = source_part

        # Parse destinations (must be numeric IDs)
        destinations = []
        for d in dest_part.split(','):
            d = d.strip()
            if d:
                try:
                    destinations.append(int(d))
                except ValueError:
                    logger.warning(f"Invalid destination ID '{d}' in route: {rule}")

        if not destinations:
            logger.warning(f"No valid destinations in route: {rule}")
            continue

        routes.append(Route(source=source, destinations=destinations, topic_id=topic_id, copy_media=copy_media))

    return routes


def parse_routes() -> List[Route]:
    """
    Parse routing configuration.

    If CHANNEL_ROUTES is set, parse it for per-source routing.
    Otherwise, build all-to-all routes from SOURCE_CHANNELS + DESTINATION_CHANNEL_IDS (legacy).
    """
    if CHANNEL_ROUTES:
        routes = _parse_channel_routes(CHANNEL_ROUTES)
        if routes:
            logger.info(f"Loaded {len(routes)} route(s) from CHANNEL_ROUTES")
            return routes
        logger.warning("CHANNEL_ROUTES set but no valid routes parsed, falling back to legacy config")

    # Legacy: all sources -> all destinations
    sources = parse_source_channels()
    destinations = parse_destination_channels()
    routes = []
    for src in sources:
        routes.append(Route(source=src, destinations=list(destinations), topic_id=None))
    return routes


# =============================================================================
# DESTINATION CHANNEL VALIDATION
# =============================================================================

@dataclass
class ValidatedDestination:
    """A validated destination channel with cached entity."""
    channel_id: int
    entity: object  # Cached Telethon entity
    title: str


async def resolve_destination_entity(client: TelegramClient, channel_id: int) -> Optional[object]:
    """
    Attempt to resolve a channel ID to a Telethon entity.

    Tries multiple strategies:
    1. Direct lookup by ID
    2. Lookup with -100 prefix (for supergroups/channels)
    3. Search in user's dialogs
    """
    # Strategy 1: Try direct lookup
    try:
        entity = await client.get_entity(channel_id)
        return entity
    except ValueError:
        pass  # ID not found, try other strategies
    except Exception:
        pass  # Other errors, try other strategies

    # Strategy 2: Try with -100 prefix (supergroups/channels use this format)
    if channel_id > 0:
        try:
            prefixed_id = int(f"-100{channel_id}")
            entity = await client.get_entity(prefixed_id)
            return entity
        except Exception:
            pass

    # Strategy 3: Search in dialogs
    try:
        async for dialog in client.iter_dialogs():
            if dialog.entity.id == channel_id:
                return dialog.entity
    except Exception:
        pass

    return None


async def validate_destination_channels(
    client: TelegramClient,
    destination_ids: List[int]
) -> Dict[int, ValidatedDestination]:
    """
    Validate all destination channels at startup.

    Returns a dict mapping channel_id -> ValidatedDestination.
    Exits with error if any channel cannot be validated.
    """
    validated = {}
    errors = []

    for dest_id in destination_ids:
        try:
            entity = await resolve_destination_entity(client, dest_id)

            if entity is None:
                errors.append(f"  ❌ {dest_id}: Channel not found. Check the ID is correct.")
                continue

            # Get channel title
            title = getattr(entity, 'title', None) or getattr(entity, 'username', None) or str(dest_id)

            # Verify we can access the channel (try to get its info)
            try:
                # This will fail if we don't have access
                await client.get_permissions(entity)
            except ChatWriteForbiddenError:
                errors.append(f"  ❌ {dest_id} ('{title}'): No permission to post. Bot account must be admin or allowed to post.")
                continue
            except UserNotParticipantError:
                errors.append(f"  ❌ {dest_id} ('{title}'): Not a member of this channel.")
                continue
            except ChannelPrivateError:
                errors.append(f"  ❌ {dest_id} ('{title}'): Private channel - no access.")
                continue
            except Exception:
                # get_permissions might not work for all channel types, that's OK
                pass

            validated[dest_id] = ValidatedDestination(
                channel_id=dest_id,
                entity=entity,
                title=title
            )
            logger.info(f"  ✅ Validated destination: '{title}' (ID: {dest_id})")

        except ChannelPrivateError:
            errors.append(f"  ❌ {dest_id}: Private channel - no access.")
        except UserNotParticipantError:
            errors.append(f"  ❌ {dest_id}: Not a member of this channel.")
        except Exception as e:
            errors.append(f"  ❌ {dest_id}: {type(e).__name__}: {e}")

    if errors:
        logger.error("")
        logger.error("╔" + "═" * 58 + "╗")
        logger.error("║" + "  ❌ DESTINATION CHANNEL VALIDATION FAILED".ljust(58) + "║")
        logger.error("╠" + "═" * 58 + "╣")
        for error in errors:
            # Split long error messages
            if len(error) > 56:
                logger.error("║" + error[:56].ljust(58) + "║")
                logger.error("║" + ("    " + error[56:])[:56].ljust(58) + "║")
            else:
                logger.error("║" + error.ljust(58) + "║")
        logger.error("╠" + "═" * 58 + "╣")
        logger.error("║" + "  Please check:".ljust(58) + "║")
        logger.error("║" + "  • Channel IDs are correct".ljust(58) + "║")
        logger.error("║" + "  • Bot account is a member of each channel".ljust(58) + "║")
        logger.error("║" + "  • Bot account has permission to post".ljust(58) + "║")
        logger.error("╚" + "═" * 58 + "╝")
        sys.exit(1)

    return validated


# =============================================================================
# MESSAGE QUEUE SYSTEM - Per-destination queues for ordered delivery
# =============================================================================

class DestinationQueue:
    """Queue for a single destination channel with retry support."""

    # Fatal errors that should not be retried
    FATAL_ERRORS = (ChannelPrivateError, UserNotParticipantError, ChatWriteForbiddenError)

    def __init__(self, validated_dest: ValidatedDestination, max_retries: int = 5, retry_delay: float = 2.0):
        self.validated_dest = validated_dest
        self.destination_id = validated_dest.channel_id  # Keep for backwards compatibility
        self.queue = asyncio.Queue()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.failed_messages = deque(maxlen=100)
        self.stats = {
            'total_received': 0,
            'total_sent': 0,
            'total_failed': 0,
        }
        self._worker_task = None
        self._client = None
        self._message_mapper = None
    
    def set_client(self, client, message_mapper=None):
        """Set the Telegram client and message mapper."""
        self._client = client
        self._message_mapper = message_mapper
    
    async def add_message(self, message, sender_title, preview, source_channel_id, reply_to_dest_id=None, copy_media=False):
        """Add a message to the queue."""
        self.stats['total_received'] += 1
        await self.queue.put({
            'message': message,
            'sender_title': sender_title,
            'preview': preview,
            'source_channel_id': source_channel_id,
            'reply_to_dest_id': reply_to_dest_id,
            'copy_media': copy_media,
            'timestamp': datetime.now(),
            'retries': 0,
        })
        queue_size = self.queue.qsize()
        if queue_size > 1:
            logger.info(f"   📥 Queued for {self.destination_id} (position: {queue_size})")
    
    async def start_worker(self):
        """Start the queue worker."""
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info(f"📋 Queue worker started for destination {self.destination_id}")
    
    async def stop_worker(self):
        """Stop the queue worker gracefully."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
    
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
                copy_media = item.get('copy_media', False)
                retries = item['retries']

                # Text-only mode: skip media-only messages (no text content)
                if not copy_media and not message.text:
                    logger.info(f"   ⏭️  Skipped media-only for '{self.validated_dest.title}'")
                    self.queue.task_done()
                    continue

                success = False

                while not success and retries < self.max_retries:
                    try:
                        if copy_media and message.media:
                            # Download & re-upload to avoid "forward from protected chat" errors
                            media_bytes = await self._client.download_media(message, bytes)
                            caption = message.text or ''
                            entities = message.entities
                            if len(caption) > 1024:
                                caption = caption[:1021] + '...'
                                # Filter entities to fit truncated caption
                                if entities:
                                    filtered = []
                                    for e in entities:
                                        if e.offset >= len(caption):
                                            continue
                                        if e.offset + e.length > len(caption):
                                            e = type(e)(offset=e.offset, length=len(caption) - e.offset, **{
                                                k: v for k, v in e.to_dict().items()
                                                if k not in ('_', 'offset', 'length')
                                            })
                                        filtered.append(e)
                                    entities = filtered if filtered else None

                            # Extract original file attributes (name, dimensions, duration, etc.)
                            file_attributes = []
                            force_document = False
                            doc = getattr(message, 'document', None) or getattr(getattr(message, 'media', None), 'document', None)
                            if doc and hasattr(doc, 'attributes'):
                                for attr in doc.attributes:
                                    if isinstance(attr, (DocumentAttributeFilename, DocumentAttributeAudio,
                                                         DocumentAttributeVideo, DocumentAttributeAnimated,
                                                         DocumentAttributeSticker)):
                                        file_attributes.append(attr)
                                # If it was sent as a document (not compressed photo), keep it as document
                                if not any(isinstance(attr, (DocumentAttributeVideo, DocumentAttributeAnimated,
                                                             DocumentAttributeSticker)) for attr in doc.attributes):
                                    if any(isinstance(attr, DocumentAttributeFilename) for attr in doc.attributes):
                                        force_document = True

                            sent_message = await self._client.send_file(
                                entity=self.validated_dest.entity,
                                file=media_bytes,
                                caption=caption,
                                formatting_entities=entities,
                                reply_to=reply_to_dest_id,
                                attributes=file_attributes if file_attributes else None,
                                force_document=force_document
                            )
                        elif copy_media:
                            # copy_media route but no actual media (text-only message)
                            sent_message = await self._client.send_message(
                                entity=self.validated_dest.entity,
                                message=message.text,
                                formatting_entities=message.entities,
                                reply_to=reply_to_dest_id
                            )
                        else:
                            # Text only — send text with formatting entities
                            sent_message = await self._client.send_message(
                                entity=self.validated_dest.entity,
                                message=message.text,
                                formatting_entities=message.entities,
                                reply_to=reply_to_dest_id
                            )
                        success = True
                        self.stats['total_sent'] += 1

                        # Save mapping to database
                        if self._message_mapper and sent_message:
                            await self._message_mapper.add_mapping(
                                source_msg_id=message.id,
                                destination_msg_id=sent_message.id,
                                source_channel_id=source_channel_id,
                                destination_channel_id=self.destination_id
                            )

                        logger.info(f"   ✅ COPIED to '{self.validated_dest.title}'")

                    except self.FATAL_ERRORS as e:
                        # Fatal peer errors - don't retry, log and skip
                        logger.error(f"   ❌ FATAL for '{self.validated_dest.title}': {type(e).__name__} - {e}")
                        logger.error(f"      This is a configuration/access issue, not retrying.")
                        self.stats['total_failed'] += 1
                        self.failed_messages.append({
                            'preview': preview,
                            'sender': sender_title,
                            'error': f"FATAL: {type(e).__name__}: {e}",
                            'timestamp': item['timestamp'],
                        })
                        break  # Exit retry loop for fatal errors

                    except Exception as e:
                        retries += 1
                        if retries < self.max_retries:
                            logger.warning(f"   ⚠️  Retry {retries}/{self.max_retries} for '{self.validated_dest.title}' - Error: {e}")
                            await asyncio.sleep(self.retry_delay * retries)
                        else:
                            logger.error(f"   ❌ FAILED for '{self.validated_dest.title}' after {self.max_retries} retries: {e}")
                            self.stats['total_failed'] += 1
                            self.failed_messages.append({
                                'preview': preview,
                                'sender': sender_title,
                                'error': str(e),
                                'timestamp': item['timestamp'],
                            })
                
                self.queue.task_done()
                
            except asyncio.CancelledError:
                remaining = self.queue.qsize()
                if remaining > 0:
                    logger.warning(f"⚠️  {remaining} messages still in queue for {self.destination_id}!")
                raise


class MessageQueueManager:
    """Manages multiple destination queues."""

    def __init__(self, validated_destinations: Dict[int, ValidatedDestination], max_retries: int = 5, retry_delay: float = 2.0):
        self.validated_destinations = validated_destinations
        self.destination_ids = list(validated_destinations.keys())
        self.queues: Dict[int, DestinationQueue] = {
            dest_id: DestinationQueue(validated_dest, max_retries, retry_delay)
            for dest_id, validated_dest in validated_destinations.items()
        }
        self.global_stats = {
            'total_received': 0,
            'total_blocked': 0,
            'total_edited': 0,
            'total_deleted': 0,
        }
    
    def set_client(self, client, message_mapper=None):
        """Set the Telegram client for all queues."""
        for queue in self.queues.values():
            queue.set_client(client, message_mapper)
    
    async def broadcast_message(self, message, sender_title, preview, source_channel_id, reply_to_dest_ids: Dict[int, int] = None):
        """Add a message to all destination queues."""
        self.global_stats['total_received'] += 1

        for dest_id, queue in self.queues.items():
            reply_to_dest_id = reply_to_dest_ids.get(dest_id) if reply_to_dest_ids else None
            await queue.add_message(
                message=message,
                sender_title=sender_title,
                preview=preview,
                source_channel_id=source_channel_id,
                reply_to_dest_id=reply_to_dest_id
            )

    async def route_message(self, message, sender_title, preview, source_channel_id, destination_ids: List[int], reply_to_dest_ids: Dict[int, int] = None, media_dest_ids: set = None):
        """Add a message to specific destination queues (per-source routing)."""
        self.global_stats['total_received'] += 1

        for dest_id in destination_ids:
            queue = self.queues.get(dest_id)
            if queue:
                reply_to_dest_id = reply_to_dest_ids.get(dest_id) if reply_to_dest_ids else None
                copy_media = dest_id in media_dest_ids if media_dest_ids else False
                await queue.add_message(
                    message=message,
                    sender_title=sender_title,
                    preview=preview,
                    source_channel_id=source_channel_id,
                    reply_to_dest_id=reply_to_dest_id,
                    copy_media=copy_media
                )
    
    async def start_workers(self):
        """Start all queue workers."""
        for queue in self.queues.values():
            await queue.start_worker()
        logger.info(f"📋 All {len(self.queues)} queue workers started")
    
    async def stop_workers(self):
        """Stop all queue workers."""
        for queue in self.queues.values():
            await queue.stop_worker()
        logger.info("📋 All queue workers stopped")
        self._log_stats()
    
    def _log_stats(self):
        """Log final statistics."""
        total_sent = sum(q.stats['total_sent'] for q in self.queues.values())
        total_failed = sum(q.stats['total_failed'] for q in self.queues.values())
        
        logger.info("")
        logger.info("╔" + "═" * 58 + "╗")
        logger.info("║" + "  📊 SESSION STATISTICS".ljust(58) + "║")
        logger.info("╠" + "═" * 58 + "╣")
        logger.info("║" + f"  Messages received: {self.global_stats['total_received']}".ljust(58) + "║")
        logger.info("║" + f"  Messages sent (total): {total_sent}".ljust(58) + "║")
        logger.info("║" + f"  Messages edited: {self.global_stats['total_edited']}".ljust(58) + "║")
        logger.info("║" + f"  Messages deleted: {self.global_stats['total_deleted']}".ljust(58) + "║")
        logger.info("║" + f"  Messages blocked: {self.global_stats['total_blocked']}".ljust(58) + "║")
        logger.info("║" + f"  Messages failed: {total_failed}".ljust(58) + "║")
        logger.info("╠" + "═" * 58 + "╣")
        for dest_id, queue in self.queues.items():
            title = queue.validated_dest.title[:20] if len(queue.validated_dest.title) > 20 else queue.validated_dest.title
            logger.info("║" + f"  → {title}: {queue.stats['total_sent']} sent, {queue.stats['total_failed']} failed".ljust(58) + "║")
        logger.info("╚" + "═" * 58 + "╝")


# =============================================================================
# FORUM TOPIC HELPER
# =============================================================================

def get_topic_id_from_message(message) -> Optional[int]:
    """
    Extract the forum topic ID from a message, if any.

    In Telethon, forum messages have message.reply_to with forum_topic=True.
    The topic ID is reply_to.reply_to_top_id (for replies within a topic)
    or reply_to.reply_to_msg_id (for the first message in a topic thread).
    Returns None for non-forum messages.
    """
    reply_to = getattr(message, 'reply_to', None)
    if reply_to is None:
        return None
    if not getattr(reply_to, 'forum_topic', False):
        return None
    # reply_to_top_id is set for replies within a topic thread
    top_id = getattr(reply_to, 'reply_to_top_id', None)
    if top_id is not None:
        return top_id
    # Otherwise, reply_to_msg_id points to the topic service message
    return getattr(reply_to, 'reply_to_msg_id', None)


# =============================================================================
# MAIN BOT LOGIC
# =============================================================================

async def main():
    """Main bot function."""
    validate_config()

    routes = parse_routes()
    if not routes:
        logger.error("No valid routes configured!")
        sys.exit(1)

    # Collect all unique destination IDs across all routes
    destination_ids = list({d for route in routes for d in route.destinations})

    if not destination_ids:
        logger.error("No valid destination channels configured!")
        sys.exit(1)

    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + "  📡 TELEGRAM CHANNEL COPIER".ljust(58) + "║")
    logger.info("╠" + "═" * 58 + "╣")
    logger.info("║" + f"  Routes: {len(routes)} configured".ljust(58) + "║")
    for route in routes:
        topic_str = f"/topic:{route.topic_id}" if route.topic_id else ""
        dest_str = ",".join(str(d) for d in route.destinations)
        line = f"    {route.source}{topic_str} -> {dest_str}"
        logger.info("║" + line[:56].ljust(58) + "║")
    logger.info("║" + f"  Destinations: {len(destination_ids)} unique channel(s)".ljust(58) + "║")
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
    logger.info("║" + f"  📋 MESSAGE QUEUES: {len(destination_ids)} (one per destination)".ljust(58) + "║")
    logger.info("║" + "  🔄 Max retries: 5".ljust(58) + "║")

    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")
    
    # Initialize client with persistent SQLite session + catch_up=True.
    # StringSession doesn't persist pts (update state) per channel, so on restart
    # Telethon detects a "gap" for supergroups and calls getChannelDifference(),
    # which can block updates for ~7 minutes. A SQLite session file persists the
    # pts state, and catch_up=True loads per-channel pts at connect time, so the
    # _message_box already knows channel states before the update loop begins.
    if not os.path.exists(f'{SESSION_FILE}.session') and TELEGRAM_STRING_SESSION:
        # First run: bootstrap SQLite session file from StringSession
        logger.info("Bootstrapping SQLite session from StringSession...")
        string_session = StringSession(TELEGRAM_STRING_SESSION)
        # Create a temporary client with SQLite session, copy auth data from StringSession
        bootstrap_client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
        bootstrap_client.session.set_dc(
            string_session.dc_id,
            string_session.server_address,
            string_session.port
        )
        bootstrap_client.session.auth_key = string_session.auth_key
        bootstrap_client.session.save()
        del bootstrap_client
        logger.info(f"SQLite session created: {SESSION_FILE}.session")

    logger.info(f"Using persistent SQLite session: {SESSION_FILE}.session")
    client = TelegramClient(
        SESSION_FILE,
        API_ID,
        API_HASH,
        sequential_updates=False,
        catch_up=True  # Load per-channel pts from SQLite session to prevent getChannelDifference delays
    )

    # message_queue_manager will be initialized after destination validation
    message_queue_manager = None

    try:
        await client.start()
        logger.info("Client connected successfully")

        # Validate destination channels before proceeding
        logger.info("Validating destination channels...")
        validated_destinations = await validate_destination_channels(client, destination_ids)
        logger.info(f"All {len(validated_destinations)} destination channel(s) validated successfully")

        # Initialize message queue manager with validated destinations
        message_queue_manager = MessageQueueManager(validated_destinations, max_retries=5, retry_delay=2.0)
        
        # Initialize message mapper (database)
        message_mapper = MessageMapper('messages.db')
        await message_mapper.init_db()
        
        # Run initial cleanup
        await message_mapper.cleanup_old(days=10)
        
        # Setup message queue manager with database
        message_queue_manager.set_client(client, message_mapper)
        await message_queue_manager.start_workers()
        
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
        
        # Build routing table: resolve source names/IDs to actual channel IDs
        # routing_table: {source_channel_id: [ResolvedRoute, ...]}
        routing_table: Dict[int, List[ResolvedRoute]] = {}

        # Collect all source identifiers we need to resolve
        source_identifiers = {route.source for route in routes}

        # Map source identifier -> resolved channel ID
        resolved_sources: Dict[Union[int, str], int] = {}

        async for dialog in client.iter_dialogs():
            channel_id = dialog.entity.id
            channel_name = dialog.name

            if channel_id in source_identifiers:
                resolved_sources[channel_id] = channel_id
                logger.info(f"✓ Matched source channel: '{channel_name}' (ID: {channel_id})")
            elif channel_name in source_identifiers:
                resolved_sources[channel_name] = channel_id
                logger.info(f"✓ Matched source channel: '{channel_name}' (ID: {channel_id})")

        # Build the routing table from resolved routes
        for route in routes:
            src_id = resolved_sources.get(route.source)
            if src_id is None:
                logger.warning(f"Source '{route.source}' not found in dialogs, skipping route")
                continue

            resolved = ResolvedRoute(
                source_channel_id=src_id,
                destinations=route.destinations,
                topic_id=route.topic_id,
                copy_media=route.copy_media
            )
            routing_table.setdefault(src_id, []).append(resolved)

        matched_channel_ids = list(routing_table.keys())

        if not matched_channel_ids:
            logger.error("No source channels found! Please check your routing configuration.")
            logger.error("Make sure the account is a member of the specified channels.")
            sys.exit(1)

        logger.info(f"Monitoring {len(matched_channel_ids)} source channel(s) with {sum(len(v) for v in routing_table.values())} route(s)")
        
        # Message deduplication cache (TTL-based)
        _seen_messages = {}  # {(channel_id, msg_id): timestamp}
        _DEDUP_TTL = 300  # 5 minutes

        def _is_duplicate(channel_id: int, msg_id: int) -> bool:
            """Return True if message was already processed recently."""
            key = (channel_id, msg_id)
            now = time.time()
            # Cleanup old entries
            expired = [k for k, t in _seen_messages.items() if now - t > _DEDUP_TTL]
            for k in expired:
                del _seen_messages[k]
            if key in _seen_messages:
                return True
            _seen_messages[key] = now
            return False

        # Register message handler
        @client.on(events.NewMessage(chats=matched_channel_ids))
        async def message_handler(event):
            try:
                message = event.message
                sender_chat = await event.get_chat()

                # Deduplication check
                if _is_duplicate(sender_chat.id, message.id):
                    logger.info(f"   ⏭️  Skipped (duplicate) msg {message.id} from {sender_chat.title}")
                    return

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

                # Determine which destinations this message should go to
                source_routes = routing_table.get(sender_chat.id, [])
                msg_topic_id = get_topic_id_from_message(message)

                # Filter routes by topic: topic_id=None matches all, specific topic matches only that topic
                target_dest_ids = set()
                media_dest_ids = set()
                for resolved_route in source_routes:
                    if resolved_route.topic_id is None or resolved_route.topic_id == msg_topic_id:
                        target_dest_ids.update(resolved_route.destinations)
                        if resolved_route.copy_media:
                            media_dest_ids.update(resolved_route.destinations)

                if not target_dest_ids:
                    if msg_topic_id is not None:
                        logger.info(f"   ⏭️  Skipped (topic {msg_topic_id} not in any route)")
                    else:
                        logger.info(f"   ⏭️  Skipped (no matching route)")
                    logger.info(f"{'─' * 50}")
                    return

                if msg_topic_id is not None:
                    logger.info(f"   📌 Forum topic: {msg_topic_id}")

                # Check for blocked words
                if BLOCKED_WORDS:
                    message_lower = text.lower()
                    for blocked_word in BLOCKED_WORDS:
                        if blocked_word in message_lower:
                            logger.warning(f"   ⛔ BLOCKED - Contains: '{blocked_word}'")
                            logger.info(f"{'─' * 50}")
                            message_queue_manager.global_stats['total_blocked'] += 1
                            return

                # Check if copy is enabled
                if not COPY_ENABLED:
                    logger.info(f"   ⏸️  DRY-RUN MODE - Message NOT copied")
                    logger.info(f"{'─' * 50}")
                    return

                # Check if this message is a reply to another message
                reply_to_dest_ids = {}
                reply_to_id = message.reply_to_msg_id
                if reply_to_id:
                    # In forums, reply_to_msg_id may point to the topic service message
                    # (not a real reply). Skip reply tracking if it's just the topic ID.
                    is_real_reply = True
                    if msg_topic_id is not None:
                        reply_to = getattr(message, 'reply_to', None)
                        top_id = getattr(reply_to, 'reply_to_top_id', None) if reply_to else None
                        if top_id is None:
                            # reply_to_msg_id points to the topic service message, not a real reply
                            is_real_reply = False

                    if is_real_reply:
                        mappings = await message_mapper.get_all_destination_mappings(
                            source_msg_id=reply_to_id,
                            source_channel_id=sender_chat.id
                        )
                        for dest_msg_id, dest_channel_id in mappings:
                            if dest_channel_id in target_dest_ids:
                                reply_to_dest_ids[dest_channel_id] = dest_msg_id

                        if reply_to_dest_ids:
                            logger.info(f"   ↩️  Reply to message #{reply_to_id} (found in {len(reply_to_dest_ids)} dest)")
                        else:
                            logger.info(f"   ↩️  Reply to message #{reply_to_id} (original not found)")

                # Route message to matched destinations only
                await message_queue_manager.route_message(
                    message=message,
                    sender_title=sender_chat.title,
                    preview=preview,
                    source_channel_id=sender_chat.id,
                    destination_ids=list(target_dest_ids),
                    reply_to_dest_ids=reply_to_dest_ids,
                    media_dest_ids=media_dest_ids
                )
                logger.info(f"   📤 Routed to {len(target_dest_ids)} destination(s)")
                logger.info(f"{'─' * 50}")

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
                
                # Get all destination mappings from database
                mappings = await message_mapper.get_all_destination_mappings(
                    source_msg_id=message.id,
                    source_channel_id=sender_chat.id
                )
                
                if not mappings:
                    logger.debug(f"No mapping found for edited message {message.id}")
                    return
                
                # Get message preview
                text = message.text or ''
                preview = text[:50].replace('\n', ' ') if text else '[Media/No text]'
                if len(text) > 50:
                    preview += '...'
                
                # Edit the message in all destinations
                edit_count = 0
                for dest_msg_id, dest_channel_id in mappings:
                    try:
                        await client.edit_message(
                            entity=dest_channel_id,
                            message=dest_msg_id,
                            text=message.text
                        )
                        edit_count += 1
                    except MessageNotModifiedError:
                        edit_count += 1  # Content already matches, count as success
                    except Exception as e:
                        logger.error(f"❌ Failed to edit message {dest_msg_id} in {dest_channel_id}: {e}")
                
                message_queue_manager.global_stats['total_edited'] += 1
                logger.info(f"{'─' * 50}")
                logger.info(f"✏️  MESSAGE EDITED")
                logger.info(f"   From: {sender_chat.title}")
                logger.info(f"   Preview: {preview}")
                logger.info(f"   ✅ EDIT synced to {edit_count}/{len(mappings)} destinations")
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
                        dest_mappings = await message_mapper.get_destination_ids(
                            source_msg_ids=deleted_ids,
                            source_channel_id=source_channel_id
                        )
                        if dest_mappings:
                            channel_id = source_channel_id
                            break
                
                if not channel_id or channel_id not in matched_channel_ids:
                    return
                
                # Get all destination mappings from database
                dest_mappings = await message_mapper.get_destination_ids(
                    source_msg_ids=deleted_ids,
                    source_channel_id=channel_id
                )
                
                if not dest_mappings:
                    return
                
                # Delete messages in all destinations
                delete_count = 0
                for dest_msg_id, dest_channel_id in dest_mappings:
                    try:
                        await client.delete_messages(
                            entity=dest_channel_id,
                            message_ids=[dest_msg_id]
                        )
                        delete_count += 1
                    except Exception as e:
                        logger.error(f"❌ Failed to delete message {dest_msg_id} in {dest_channel_id}: {e}")
                
                message_queue_manager.global_stats['total_deleted'] += 1
                
                # Remove mappings from database
                await message_mapper.delete_mappings(
                    source_msg_ids=deleted_ids,
                    source_channel_id=channel_id
                )
                
                logger.info(f"{'─' * 50}")
                logger.info(f"🗑️  MESSAGE(S) DELETED")
                logger.info(f"   Count: {delete_count}")
                logger.info(f"   ✅ DELETE synced to all destinations")
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

        if message_queue_manager is not None:
            await message_queue_manager.stop_workers()
        
        # Close database
        if 'message_mapper' in locals():
            await message_mapper.close()
        
        await client.disconnect()
        logger.info("Client disconnected")


if __name__ == "__main__":
    asyncio.run(main())
