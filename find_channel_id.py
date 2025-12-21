"""
Script per trovare l'ID di un canale Telegram.
Cerca il canale "MONEY HOUSE 🏠💰" e stampa il suo ID.
"""

from telethon import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Telegram API credentials
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
TELEGRAM_STRING_SESSION = os.getenv('TELEGRAM_STRING_SESSION')

# Canale da cercare
TARGET_CHANNEL = "MONEY HOUSE 🏠💰"


async def find_channel():
    """Cerca il canale e stampa il suo ID."""
    
    if not all([API_ID, API_HASH, TELEGRAM_STRING_SESSION]):
        print("❌ Errore: Assicurati di avere API_ID, API_HASH e TELEGRAM_STRING_SESSION nel file .env")
        return
    
    client = TelegramClient(
        StringSession(TELEGRAM_STRING_SESSION),
        API_ID,
        API_HASH
    )
    
    try:
        await client.start()
        print("✓ Connesso a Telegram\n")
        print("=" * 60)
        print("RICERCA CANALI")
        print("=" * 60)
        
        found = False
        all_channels = []
        
        async for dialog in client.iter_dialogs():
            channel_id = dialog.entity.id
            channel_name = dialog.name
            
            all_channels.append((channel_name, channel_id))
            
            # Cerca il canale target
            if TARGET_CHANNEL.lower() in channel_name.lower():
                print(f"\n🎯 TROVATO!")
                print(f"   Nome: {channel_name}")
                print(f"   ID: {channel_id}")
                print(f"\n📋 Copia questo valore nel file .env:")
                print(f"   DESTINATION_CHANNEL_ID={channel_id}")
                found = True
        
        if not found:
            print(f"\n❌ Canale '{TARGET_CHANNEL}' non trovato.")
            print("\n📋 Ecco tutti i canali/gruppi disponibili:\n")
            for name, cid in all_channels:
                print(f"   • {name} (ID: {cid})")
            print(f"\n💡 Assicurati che l'account sia membro del canale '{TARGET_CHANNEL}'")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"❌ Errore: {e}")
    finally:
        await client.disconnect()
        print("Disconnesso.")


if __name__ == "__main__":
    asyncio.run(find_channel())
