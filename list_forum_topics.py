"""
Script per elencare tutti i topic (canali interni) di un super-gruppo Telegram con forum.
"""

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.types import Channel
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Telegram API credentials
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
TELEGRAM_STRING_SESSION = os.getenv("TELEGRAM_STRING_SESSION")

# ID del super-gruppo (senza il -100 prefix)
SUPERGROUP_ID = 3354980634


async def list_forum_topics():
    """Elenca tutti i topic del forum nel super-gruppo."""

    if not all([API_ID, API_HASH, TELEGRAM_STRING_SESSION]):
        print(
            "❌ Errore: Assicurati di avere API_ID, API_HASH e TELEGRAM_STRING_SESSION nel file .env"
        )
        return

    client = TelegramClient(StringSession(TELEGRAM_STRING_SESSION), API_ID, API_HASH)

    try:
        await client.start()
        print("✓ Connesso a Telegram\n")
        print("=" * 60)
        print("RICERCA TOPIC DEL FORUM")
        print("=" * 60)

        # Prova a ottenere l'entità del super-gruppo
        try:
            # Prova con l'ID negativo (formato standard per gruppi)
            entity = await client.get_entity(-100 * 10 + SUPERGROUP_ID)
        except Exception:
            try:
                # Prova con il prefisso -100
                entity = await client.get_entity(int(f"-100{SUPERGROUP_ID}"))
            except Exception:
                try:
                    # Prova con l'ID diretto
                    entity = await client.get_entity(SUPERGROUP_ID)
                except Exception as e:
                    print(f"❌ Impossibile trovare il gruppo: {e}")
                    print("\n💡 Cercando nei dialoghi...")
                    
                    # Cerca nei dialoghi
                    async for dialog in client.iter_dialogs():
                        if str(dialog.entity.id) == str(SUPERGROUP_ID) or str(dialog.entity.id).endswith(str(SUPERGROUP_ID)):
                            entity = dialog.entity
                            print(f"✓ Trovato: {dialog.name}")
                            break
                    else:
                        print("❌ Gruppo non trovato nei dialoghi")
                        return

        print(f"\n📌 Gruppo: {getattr(entity, 'title', 'N/A')}")
        print(f"📌 ID: {entity.id}")
        print(f"📌 È un forum: {getattr(entity, 'forum', False)}")

        if not getattr(entity, 'forum', False):
            print("\n⚠️  Questo gruppo non ha i topic del forum attivati.")
            print("    I 'canali interni' sono disponibili solo nei gruppi con forum attivo.")
            return

        # Ottieni i topic del forum
        print("\n📋 Topic del forum:\n")
        
        offset_date = 0
        offset_id = 0
        offset_topic = 0
        
        result = await client(GetForumTopicsRequest(
            channel=entity,
            offset_date=offset_date,
            offset_id=offset_id,
            offset_topic=offset_topic,
            limit=100
        ))
        
        if result.topics:
            for topic in result.topics:
                topic_id = topic.id
                topic_title = getattr(topic, 'title', 'Generale')
                print(f"   📍 Topic ID: {topic_id}")
                print(f"      Titolo: {topic_title}")
                print()
        else:
            print("   Nessun topic trovato.")

        print("=" * 60)

    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()
        print("\nDisconnesso.")


if __name__ == "__main__":
    asyncio.run(list_forum_topics())
