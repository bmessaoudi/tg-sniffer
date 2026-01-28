"""
Database module for message mapping between source and destination channels.
Uses aiosqlite for async SQLite operations.
"""

import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

logger = logging.getLogger('tg-sniffer')


class MessageMapper:
    """
    Manages source-to-destination message ID mappings in SQLite.
    
    Schema:
        - id: INTEGER PRIMARY KEY
        - source_msg_id: INTEGER (message ID in source channel)
        - destination_msg_id: INTEGER (message ID in destination channel)
        - source_channel_id: INTEGER (source channel ID)
        - destination_channel_id: INTEGER (destination channel ID)
        - created_at: TIMESTAMP (when the mapping was created)
    """
    
    def __init__(self, db_path: str = 'messages.db'):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
    
    async def init_db(self) -> None:
        """Initialize the database connection and create tables if needed."""
        self._db = await aiosqlite.connect(self.db_path)
        
        # Enable WAL mode for better concurrent access
        await self._db.execute('PRAGMA journal_mode=WAL')
        
        # Check if destination_channel_id column exists (migration)
        async with self._db.execute("PRAGMA table_info(message_mappings)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
        
        if 'destination_channel_id' not in column_names and columns:
            # Migration: add destination_channel_id column
            logger.info("🔄 Migrating database: adding destination_channel_id column...")
            await self._db.execute('''
                ALTER TABLE message_mappings 
                ADD COLUMN destination_channel_id INTEGER DEFAULT 0
            ''')
            await self._db.commit()
            logger.info("✅ Database migration completed")
        
        # Create the message mappings table (if not exists)
        await self._db.execute('''
            CREATE TABLE IF NOT EXISTS message_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_msg_id INTEGER NOT NULL,
                destination_msg_id INTEGER NOT NULL,
                source_channel_id INTEGER NOT NULL,
                destination_channel_id INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for fast lookups
        await self._db.execute('''
            CREATE INDEX IF NOT EXISTS idx_source_dest_msg 
            ON message_mappings(source_msg_id, source_channel_id, destination_channel_id)
        ''')
        
        await self._db.commit()
        logger.info("💾 Database initialized successfully")
    
    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("💾 Database connection closed")
    
    async def add_mapping(
        self, 
        source_msg_id: int, 
        destination_msg_id: int, 
        source_channel_id: int,
        destination_channel_id: int
    ) -> None:
        """
        Add a new message mapping.
        
        Args:
            source_msg_id: Message ID in the source channel
            destination_msg_id: Message ID in the destination channel
            source_channel_id: ID of the source channel
            destination_channel_id: ID of the destination channel
        """
        await self._db.execute(
            '''
            INSERT INTO message_mappings 
            (source_msg_id, destination_msg_id, source_channel_id, destination_channel_id)
            VALUES (?, ?, ?, ?)
            ''',
            (source_msg_id, destination_msg_id, source_channel_id, destination_channel_id)
        )
        await self._db.commit()
        logger.debug(f"💾 Mapping saved: {source_msg_id} → {destination_msg_id} (dest: {destination_channel_id})")
    
    async def get_destination_id(
        self, 
        source_msg_id: int, 
        source_channel_id: int,
        destination_channel_id: int
    ) -> Optional[int]:
        """
        Get the destination message ID for a source message in a specific destination channel.
        
        Args:
            source_msg_id: Message ID in the source channel
            source_channel_id: ID of the source channel
            destination_channel_id: ID of the destination channel
            
        Returns:
            The destination message ID, or None if not found
        """
        async with self._db.execute(
            '''
            SELECT destination_msg_id FROM message_mappings
            WHERE source_msg_id = ? AND source_channel_id = ? AND destination_channel_id = ?
            ''',
            (source_msg_id, source_channel_id, destination_channel_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def get_all_destination_mappings(
        self, 
        source_msg_id: int, 
        source_channel_id: int
    ) -> List[Tuple[int, int]]:
        """
        Get all destination mappings for a source message.
        
        Args:
            source_msg_id: Message ID in the source channel
            source_channel_id: ID of the source channel
            
        Returns:
            List of tuples (destination_msg_id, destination_channel_id)
        """
        async with self._db.execute(
            '''
            SELECT destination_msg_id, destination_channel_id FROM message_mappings
            WHERE source_msg_id = ? AND source_channel_id = ?
            ''',
            (source_msg_id, source_channel_id)
        ) as cursor:
            rows = await cursor.fetchall()
            return [(row[0], row[1]) for row in rows]
    
    async def get_destination_ids(
        self, 
        source_msg_ids: List[int], 
        source_channel_id: int
    ) -> List[Tuple[int, int]]:
        """
        Get destination message IDs for multiple source messages.
        
        Args:
            source_msg_ids: List of message IDs in the source channel
            source_channel_id: ID of the source channel
            
        Returns:
            List of tuples (destination_msg_id, destination_channel_id)
        """
        if not source_msg_ids:
            return []
        
        placeholders = ','.join('?' * len(source_msg_ids))
        async with self._db.execute(
            f'''
            SELECT destination_msg_id, destination_channel_id FROM message_mappings
            WHERE source_msg_id IN ({placeholders}) AND source_channel_id = ?
            ''',
            (*source_msg_ids, source_channel_id)
        ) as cursor:
            rows = await cursor.fetchall()
            return [(row[0], row[1]) for row in rows]
    
    async def delete_mapping(
        self, 
        source_msg_id: int, 
        source_channel_id: int,
        destination_channel_id: int
    ) -> None:
        """
        Delete a message mapping for a specific destination.
        
        Args:
            source_msg_id: Message ID in the source channel
            source_channel_id: ID of the source channel
            destination_channel_id: ID of the destination channel
        """
        await self._db.execute(
            '''
            DELETE FROM message_mappings
            WHERE source_msg_id = ? AND source_channel_id = ? AND destination_channel_id = ?
            ''',
            (source_msg_id, source_channel_id, destination_channel_id)
        )
        await self._db.commit()
        logger.debug(f"💾 Mapping deleted for source message: {source_msg_id}")
    
    async def delete_mappings(
        self, 
        source_msg_ids: List[int], 
        source_channel_id: int
    ) -> None:
        """
        Delete all message mappings for given source message IDs.
        
        Args:
            source_msg_ids: List of message IDs in the source channel
            source_channel_id: ID of the source channel
        """
        if not source_msg_ids:
            return
        
        placeholders = ','.join('?' * len(source_msg_ids))
        await self._db.execute(
            f'''
            DELETE FROM message_mappings
            WHERE source_msg_id IN ({placeholders}) AND source_channel_id = ?
            ''',
            (*source_msg_ids, source_channel_id)
        )
        await self._db.commit()
        logger.debug(f"💾 Deleted mappings for {len(source_msg_ids)} source messages")
    
    async def cleanup_old(self, days: int = 5) -> int:
        """
        Remove mappings older than the specified number of days.
        
        Args:
            days: Number of days after which to delete old mappings
            
        Returns:
            Number of deleted records
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Get count before deletion
        async with self._db.execute(
            'SELECT COUNT(*) FROM message_mappings WHERE created_at < ?',
            (cutoff_date,)
        ) as cursor:
            row = await cursor.fetchone()
            count = row[0] if row else 0
        
        if count > 0:
            await self._db.execute(
                'DELETE FROM message_mappings WHERE created_at < ?',
                (cutoff_date,)
            )
            await self._db.commit()
            logger.info(f"🧹 Cleaned up {count} old message mappings (older than {days} days)")
        
        return count
    
    async def get_stats(self) -> dict:
        """Get database statistics."""
        async with self._db.execute(
            'SELECT COUNT(*) FROM message_mappings'
        ) as cursor:
            row = await cursor.fetchone()
            total = row[0] if row else 0
        
        # Count unique destination channels
        async with self._db.execute(
            'SELECT COUNT(DISTINCT destination_channel_id) FROM message_mappings'
        ) as cursor:
            row = await cursor.fetchone()
            dest_count = row[0] if row else 0
        
        return {
            'total_mappings': total,
            'destination_channels': dest_count,
            'db_path': self.db_path
        }
