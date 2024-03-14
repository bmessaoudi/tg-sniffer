from telethon import TelegramClient, functions, events
from telethon.sessions import StringSession

API_ID = "21043880"
API_HASH = "a2eb61ac67a41d35b1e96d61616da135"
TELEGRAM_STRING_SESSION = "1BJWap1wBuxBYEaqEaC7bR9KwTnFmcRSbzx1YMGv_tyA2vKqC4PWmqhv-GdcmrI3Pz6K4RrShytQiaE68ltVQrMrTHgtnStd1k479UR-boPBBiDhHmmRQfLgfzYcnoZzk3t6Ydc8wDWM8_vVOd17S9bBEnR-8GzfajBfv5-OF-4ccLn2a1WzN9N0FTz1M6EkD5jQjv2CsgA0IOz4FG9StPOTPGrbEWIqEYnmAZaIDDZS8Nd-MSxC_-zlx-nwcMb0ZAuDqdLv0cxyJ2RzTs6Zmb57MGm_uxdMRjd8ae_HykCOH5DMhUh63EOODiOOgpLyD8LzpmHdjn4-FJfncwgPeybwZykSNgG4="

client = TelegramClient(StringSession(
    TELEGRAM_STRING_SESSION), API_ID, API_HASH)
chat_ids = []
chat_names = ['FXpro: Delta', 'Oblivion']
channel_destination = 'IGENIUS 15 DAYS TRIAL'


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

    chat_id_destination = 1001912225575
    result = await client(functions.contacts.SearchRequest(q=channel_destination, limit=1))
    if result.my_results and result.my_results[0].channel_id:
        chat_id_destination = result.my_results[0].channel_id

    @events.register(events.NewMessage(chats=[chat_ids]))
    async def sniffer(event):
        print('MESSAGE EVENT: ' + str(event))
        message_text = event.message.message
        await client.send_message(entity=chat_id_destination, message=message_text)

    client.add_event_handler(sniffer)

    print('Start sniffing')

    await client.run_until_disconnected()

client.loop.run_until_complete(main())
