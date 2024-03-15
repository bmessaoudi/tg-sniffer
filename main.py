from telethon import TelegramClient, functions, events
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[
                        logging.FileHandler("output.log"),
                        logging.StreamHandler()
                    ])

load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
TELEGRAM_STRING_SESSION = os.getenv('TELEGRAM_STRING_SESSION')

client = TelegramClient(StringSession(
    TELEGRAM_STRING_SESSION), API_ID, API_HASH)
chat_ids = []
chat_names = ['FXpro: Delta', 'Oblivion', 'Test crypto botty']
# chat_names = ['Test crypto botty']
chat_destination = -1002135583752


async def main():
    global chat_id_destination
    try:
        logging.info('Bot started')
        await client.start()

        for name in chat_names:
            logging.info('Search chat ID of: ' + name)
            result = await client(functions.contacts.SearchRequest(q=name, limit=1))
            if result.my_results and result.my_results[0].channel_id:
                logging.info(
                    'Founded: ' + str(result.my_results[0].channel_id))
                chat_ids.append(result.my_results[0].channel_id)
            else:
                logging.warning('Not founded')

        @events.register(events.NewMessage(chats=chat_ids))
        async def sniffer(event):
            logging.info('MESSAGE EVENT: ' + str(event))
            message_text = event.message.message
            await client.send_message(entity=chat_destination, message=message_text)

        client.add_event_handler(sniffer)

        logging.info('Start sniffing')

        await client.run_until_disconnected()
    except Exception as e:
        logging.error(e)

client.loop.run_until_complete(main())
