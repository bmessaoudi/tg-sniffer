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
chat_names = ['FXpro: Athena']
chat_destination = -1002236481077


async def main():
    global chat_id_destination
    try:
        logging.info('Bot started')
        await client.start()

        async for d in client.iter_dialogs():
            channelId = d.entity.id
            channelName = d.name
            if (channelName in chat_names):
                logging.info(
                    f"Channel id: {channelId}, channel name: {channelName}")
                chat_ids.append(channelId)

        @events.register(events.NewMessage(chats=chat_ids))
        async def sniffer(event):
            logging.info('MESSAGE EVENT: ' + str(event))
            message = event.message
            await client.send_message(entity=chat_destination, message=message)

        client.add_event_handler(sniffer)

        logging.info('Start sniffing')

        await client.run_until_disconnected()
    except Exception as e:
        logging.error(e)

client.loop.run_until_complete(main())
