from telethon import TelegramClient, functions, events
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
TELEGRAM_STRING_SESSION = os.getenv('TELEGRAM_STRING_SESSION')

client = TelegramClient(StringSession(
    TELEGRAM_STRING_SESSION), API_ID, API_HASH)
chat_ids = []
chat_names = ['FXpro: Delta', 'Oblivion']


async def main():
    print('Bot started')
    await client.start()

    for name in chat_names:
        print('Search chat id of: ' + name)
        result = await client(functions.contacts.SearchRequest(q=name, limit=1))
        if result.my_results and result.my_results[0].channel_id:
            print('Founded: ' + str(result.my_results[0].channel_id))
            chat_ids.append(result.my_results[0].channel_id)
        else:
            print('Not founded')

    @events.register(events.NewMessage(chats=[chat_ids]))
    async def sniffer(event):
        print('MESSAGE EVENT: ' + str(event))
        message_text = event.message.message
        await client.send_message(entity=-1001912225575, message=message_text)

    client.add_event_handler(sniffer)

    print('Start sniffing')

    await client.run_until_disconnected()

client.loop.run_until_complete(main())
