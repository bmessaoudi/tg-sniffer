"""
Telegram Session String Generator
==================================
Questo script genera una Session String per l'autenticazione Telegram.
Usa il tuo API_ID/API_HASH ma fa login con l'account del cliente.

Uso:
    python generate_session.py
"""

from telethon import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Get API credentials from .env (your credentials)
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')


def print_banner():
    print("=" * 60)
    print("   TELEGRAM SESSION STRING GENERATOR")
    print("=" * 60)
    print()


def check_credentials():
    """Check if API credentials are set."""
    if not API_ID or not API_HASH:
        print("❌ ERRORE: API_ID e API_HASH non trovati!")
        print()
        print("Assicurati di avere un file .env con:")
        print("  API_ID=your_api_id")
        print("  API_HASH=your_api_hash")
        print()
        print("Puoi ottenere queste credenziali da: https://my.telegram.org")
        return False
    
    print(f"✅ API_ID trovato: {API_ID}")
    print(f"✅ API_HASH trovato: {API_HASH[:8]}...")
    print()
    return True


async def generate_session():
    """Generate a new session string."""
    print_banner()
    
    if not check_credentials():
        return
    
    print("Questo script genererà una Session String per un account Telegram.")
    print("Il proprietario dell'account riceverà un codice OTP.")
    print()
    print("-" * 60)
    
    # Create client with empty session (will create new one)
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    
    await client.connect()
    
    # Get phone number
    phone = input("📱 Inserisci il numero di telefono (con prefisso, es: +39...): ").strip()
    
    if not phone:
        print("❌ Numero di telefono non valido")
        return
    
    # Send code request
    print()
    print(f"📤 Invio codice OTP a {phone}...")
    
    try:
        await client.send_code_request(phone)
        print("✅ Codice inviato!")
        print()
        
        # Get the code from user
        code = input("🔑 Inserisci il codice OTP ricevuto: ").strip()
        
        if not code:
            print("❌ Codice non valido")
            return
        
        # Try to sign in
        try:
            await client.sign_in(phone, code)
        except Exception as e:
            if "Two-steps verification" in str(e) or "password" in str(e).lower():
                # 2FA is enabled
                print()
                print("🔐 Questo account ha la verifica in due passaggi attiva.")
                password = input("🔑 Inserisci la password 2FA: ").strip()
                await client.sign_in(password=password)
            else:
                raise e
        
        # Get the session string
        session_string = client.session.save()
        
        # Get user info
        me = await client.get_me()
        
        print()
        print("=" * 60)
        print("✅ LOGIN EFFETTUATO CON SUCCESSO!")
        print("=" * 60)
        print()
        print(f"👤 Account: {me.first_name} {me.last_name or ''}")
        print(f"📞 Telefono: {me.phone}")
        print(f"🆔 User ID: {me.id}")
        print()
        print("-" * 60)
        print("📋 SESSION STRING (copia questa nel tuo .env):")
        print("-" * 60)
        print()
        print(session_string)
        print()
        print("-" * 60)
        print()
        print("Aggiungi questa riga al tuo file .env:")
        print(f"TELEGRAM_STRING_SESSION={session_string}")
        print()
        print("=" * 60)
        
    except Exception as e:
        print()
        print(f"❌ Errore: {e}")
        
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(generate_session())
