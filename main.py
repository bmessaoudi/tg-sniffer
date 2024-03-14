from telethon import TelegramClient, functions, events
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

client = TelegramClient('main', API_ID, API_HASH)
chat_ids = []
chat_names = ['FXpro: Delta', 'Oblivion']

client.start()


for name in chat_names:
    result = client(functions.contacts.SearchRequest(q=name, limit=1))
    if result.my_results and result.my_results[0].channel_id:
        chat_ids.append(result.my_results[0].channel_id)


@events.register(events.NewMessage(chats=[chat_ids]))
async def sniffer(event):
    print(event)
    message_text = event.message.message
    await client.send_message(entity=-1001912225575, message=message_text)


client.add_event_handler(sniffer)
client.run_until_disconnected()
