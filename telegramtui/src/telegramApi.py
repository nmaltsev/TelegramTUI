import asyncio
import socks, os
from telethon import TelegramClient, events
from telethon.tl import types, functions
from datetime import timedelta
from telegramtui.src.config import get_config
import threading

class TelegramApi:
    client = None
    dialogs = []
    messages = []
    online = []
    me = None

    need_update_message = 0
    need_update_online = 0
    need_update_current_user = -1
    need_update_read_messages = 0

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.start_async, daemon=True)
        self.thread.start()

    def start_async(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._async_init())

    async def _async_init(self):
        config = get_config()
        api_id = config.get('telegram_api', 'api_id')
        api_hash = config.get('telegram_api', 'api_hash')
        session_name = config.get('telegram_api', 'session_name')

        self.timezone = int(config.get('other', 'timezone'))
        self.message_dialog_len = int(config.get('app', 'message_dialog_len'))

        # proxy settings
        if config.get('proxy', 'type') == "HTTP":
            proxy_type = socks.HTTP
        elif config.get('proxy', 'type') == "SOCKS4":
            proxy_type = socks.SOCKS4
        elif config.get('proxy', 'type') == "SOCKS5":
            proxy_type = socks.SOCKS5
        else:
            proxy_type = None
        proxy_addr = config.get('proxy', 'addr')
        proxy_port = int(config.get('proxy', 'port')) if config.get('proxy', 'port').isdigit() else None
        proxy_username = config.get('proxy', 'username')
        proxy_password = config.get('proxy', 'password')

        proxy = (proxy_type, proxy_addr, proxy_port, False, proxy_username, proxy_password)

        session_name = os.path.expanduser("~") + '/.config/telegramtui/' + session_name

        # create connection
        self.client = TelegramClient(
            session_name, 
            api_id, 
            api_hash, 
            system_version="4.16.30-vxCustom",
            proxy=proxy
        )
        try:
            await self.client.start()
            self.me = await self.client.get_me()
            self.dialogs = await self.client.get_dialogs(limit=self.message_dialog_len)
            self.messages = [None] * len(self.dialogs)
            self.online = [""] * len(self.dialogs)
            
            if self.dialogs:
                self.messages[0] = await self.client.get_messages(self.dialogs[0].entity, limit=self.message_dialog_len)

            # event for new messages
            @self.client.on(events.NewMessage)
            async def my_event_handler(event):
                for i in range(len(self.dialogs)):
                    if hasattr(self.dialogs[i].entity, 'user_id') and hasattr(event.message.peer_id, 'user_id') and \
                            self.dialogs[i].entity.user_id == event.message.peer_id.user_id:
                        await self.event_message(i)
                    elif hasattr(self.dialogs[i].entity, 'chat_id') and hasattr(event.message.peer_id, 'chat_id') and \
                            self.dialogs[i].entity.chat_id == event.message.peer_id.chat_id:
                        await self.event_message(i)
                    elif hasattr(self.dialogs[i].entity, 'channel_id') and hasattr(event.message.peer_id, 'channel_id') and \
                            self.dialogs[i].entity.channel_id == event.message.peer_id.channel_id:
                        await self.event_message(i)

            # event for read messages
            @self.client.on(events.MessageRead)
            async def read_event_handler(event):
                for i in range(len(self.dialogs)):
                    if hasattr(self.dialogs[i].entity, 'user_id') and hasattr(event.peer, 'user_id') and \
                            self.dialogs[i].entity.user_id == event.peer.user_id:
                        self.dialogs[i].read_outbox_max_id = event.max_id
                        self.need_update_current_user = i
                    elif hasattr(self.dialogs[i].entity, 'chat_id') and hasattr(event.peer, 'chat_id') and \
                            self.dialogs[i].entity.chat_id == event.peer.chat_id:
                        self.dialogs[i].read_outbox_max_id = event.max_id
                        self.need_update_current_user = i
                self.need_update_read_messages = 1

            # event for online/offline
            @self.client.on(events.UserUpdate)
            async def user_update_handler(event):
                user = event.user
                for i in range(len(self.dialogs)):
                    if hasattr(self.dialogs[i].entity, 'user_id') and user.id == self.dialogs[i].entity.user_id:
                        if isinstance(user.status, types.UserStatusOnline):
                            self.online[i] = "Online"
                        elif isinstance(user.status, types.UserStatusOffline):
                            self.online[i] = "Last seen at " + str(user.status.was_online + (timedelta(self.timezone) // 24))
                        else:
                            self.online[i] = ""
                        self.need_update_current_user = i
                self.need_update_online = 1

        except Exception as ex:
            print("Something wrong: " + str(ex))
            os._exit(1)

    async def event_message(self, user_id):
        if self.messages[user_id] is None:
            await self.get_messages(user_id)
            new_message = await self.client.get_messages(
                self.dialogs[user_id].entity,
                min_id=self.messages[user_id][0].id - 1
            )
        else:
            new_message = await self.client.get_messages(
                self.dialogs[user_id].entity,
                min_id=self.messages[user_id][0].id
            )

        for j in range(len(new_message) - 1, -1, -1):
            self.messages[user_id].insert(0, new_message[j])
            self.dialogs[user_id].unread_count += 1

        self.messages[user_id].sort(key=lambda x: x.id, reverse=True)
        self.remove_duplicates(self.messages[user_id])

        self.need_update_message = 1
        self.need_update_current_user = user_id

    async def get_messages(self, user_id):
        if self.messages[user_id] is None:
            data = await self.client.get_messages(
                self.dialogs[user_id].entity, 
                limit=self.message_dialog_len
            )
            self.messages[user_id] = data
            self.messages[user_id].sort(key=lambda x: x.id, reverse=True)
            return data
        else:
            return self.messages[user_id]

    async def get_message_by_id(self, user_id, message_id):
        for i in range(len(self.messages[user_id])):
            if self.messages[user_id][i].id == message_id:
                return self.messages[user_id][i]

    async def delete_message(self, user_id, message_id):
        await self.client.delete_messages(
            self.dialogs[user_id].entity, 
            [message_id]
        )

    async def download_media(self, media, path):
        return await self.client.download_media(media, path)

    async def message_send(self, message, user_id, reply=None):
        data = await self.client.send_message(
            self.dialogs[user_id].entity, 
            message, 
            reply_to=reply
        )
        await self.client.send_read_acknowledge(
            self.dialogs[user_id].entity, 
            max_id=data.id
        )

        new_message = await self.client.get_messages(
            self.dialogs[user_id].entity, 
            min_id=(data.id - 1)
        )

        for j in range(len(new_message) - 1, -1, -1):
            self.messages[user_id].insert(0, new_message[j])

        self.messages[user_id].sort(key=lambda x: x.id, reverse=True)
        self.remove_duplicates(self.messages[user_id])

    async def file_send(self, file, user_id, func):
        data = await self.client.send_file(
            self.dialogs[user_id].entity, 
            file, 
            progress_callback=func
        )

        new_message = await self.client.get_messages(
            self.dialogs[user_id].entity, 
            min_id=(data.id - 1)
        )

        for j in range(len(new_message) - 1, -1, -1):
            self.messages[user_id].insert(0, new_message[j])

        self.messages[user_id].sort(key=lambda x: x.id, reverse=True)
        self.remove_duplicates(self.messages[user_id])

    async def read_all_messages(self, user_id):
        if self.messages[user_id] and hasattr(self.messages[user_id][0], 'id'):
            await self.client.send_read_acknowledge(
                self.dialogs[user_id].entity,
                max_id=self.messages[user_id][0].id
            )

    def remove_duplicates(self, messages):
        i = 0
        while i < len(messages) - 1:
            if messages[i].id == messages[i + 1].id:
                del messages[i]
                i = i - 1

            i = i + 1

        return messages

    def run_async_task(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

# Create client instance in a thread-safe way
client = TelegramApi()