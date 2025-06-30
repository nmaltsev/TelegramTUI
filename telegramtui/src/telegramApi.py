import socks, os, asyncio
from telethon import TelegramClient, events
from datetime import timedelta
from telegramtui.src.config import get_config


class TelegramApi:
    def __init__(self):
        self.client = None
        self.dialogs = []
        self.messages = []
        self.online = []

        self.timezone = 0
        self.message_dialog_len = 50

        self.need_update_message = 0
        self.need_update_online = 0
        self.need_update_current_user = -1
        self.need_update_read_messages = 0

    async def initialize(self):
        config = get_config()
        api_id = config.get('telegram_api', 'api_id')
        api_hash = config.get('telegram_api', 'api_hash')
        workers = int(config.get('telegram_api', 'workers'))
        session_name = config.get('telegram_api', 'session_name')

        self.timezone = int(config.get('other', 'timezone'))
        self.message_dialog_len = int(config.get('app', 'message_dialog_len'))

        # Proxy setup
        proxy_type = {
            "HTTP": socks.HTTP,
            "SOCKS4": socks.SOCKS4,
            "SOCKS5": socks.SOCKS5
        }.get(config.get('proxy', 'type'), None)

        proxy_addr = config.get('proxy', 'addr')
        proxy_port = int(config.get('proxy', 'port')) if config.get('proxy', 'port').isdigit() else None
        proxy_username = config.get('proxy', 'username')
        proxy_password = config.get('proxy', 'password')

        proxy = (proxy_type, proxy_addr, proxy_port, False, proxy_username, proxy_password)

        session_path = os.path.expanduser("~") + '/.config/telegramtui/' + session_name
        self.client = TelegramClient(session_path, api_id, api_hash, proxy=proxy)

        try:
            await self.client.start()
        except Exception as ex:
            print(f"Failed to start client: {ex}")
            raise

        self.me = await self.client.get_me()
        self.dialogs = await self.client.get_dialogs(limit=self.message_dialog_len)
        self.messages = [None] * len(self.dialogs)
        self.online = [""] * len(self.dialogs)

        self.messages[0] = await self.client.get_messages(self.dialogs[0].entity, limit=self.message_dialog_len)

        # Event handlers
        @self.client.on(events.NewMessage)
        async def handler(event):
            await self._handle_new_message(event)

        @self.client.on(events.Raw)
        async def handler(event):
            await self._handle_read_event(event)

        @self.client.on(events.UserUpdate)
        async def handler(event):
            await self._handle_user_update(event)

    async def _handle_new_message(self, event):
        for i, dialog in enumerate(self.dialogs):
            peer = dialog.dialog.peer
            if hasattr(peer, 'user_id') and getattr(event._chat_peer, 'user_id', None) == peer.user_id:
                await self.event_message(i)
            elif hasattr(peer, 'chat_id') and getattr(event._chat_peer, 'chat_id', None) == peer.chat_id:
                await self.event_message(i)
            elif hasattr(peer, 'channel_id') and getattr(event._chat_peer, 'channel_id', None) == peer.channel_id:
                await self.event_message(i)

    async def _handle_read_event(self, event):
        for i, dialog in enumerate(self.dialogs):
            peer = dialog.dialog.peer
            if hasattr(peer, 'user_id') and getattr(event.peer, 'user_id', None) == peer.user_id:
                dialog.dialog.read_outbox_max_id = event.max_id
                self.need_update_current_user = i
            elif hasattr(peer, 'chat_id') and getattr(event.peer, 'chat_id', None) == peer.chat_id:
                dialog.dialog.read_outbox_max_id = event.max_id
                self.need_update_current_user = i
        self.need_update_read_messages = 1

    async def _handle_user_update(self, event):
        for i, dialog in enumerate(self.dialogs):
            peer = dialog.dialog.peer
            if hasattr(peer, 'user_id') and getattr(event._chat_peer, 'user_id', None) == peer.user_id:
                if event.online:
                    self.online[i] = "Online"
                elif event.last_seen is not None:
                    self.online[i] = "Last seen at " + str(event.last_seen + timedelta(hours=self.timezone))
                else:
                    self.online[i] = ""
                self.need_update_current_user = i
        self.need_update_online = 1

    async def event_message(self, user_id):
        if self.messages[user_id] is None:
            await self.get_messages(user_id)

        new_messages = await self.client.get_messages(self.dialogs[user_id].entity,
                                                      min_id=self.messages[user_id][0].id)

        for msg in reversed(new_messages):
            self.messages[user_id].insert(0, msg)
            self.dialogs[user_id].unread_count += 1

        self.messages[user_id].sort(key=lambda x: x.id, reverse=True)
        self.remove_duplicates(self.messages[user_id])

        self.need_update_message = 1
        self.need_update_current_user = user_id

    async def get_messages(self, user_id):
        if self.messages[user_id] is None:
            data = await self.client.get_messages(self.dialogs[user_id].entity, limit=self.message_dialog_len)
            self.messages[user_id] = sorted(data, key=lambda x: x.id, reverse=True)
            return data
        return self.messages[user_id]

    def get_message_by_id(self, user_id, message_id):
        for msg in self.messages[user_id]:
            if msg.id == message_id:
                return msg

    async def delete_message(self, user_id, message_id):
        await self.client.delete_messages(self.dialogs[user_id].entity, message_id)

    async def download_media(self, media, path):
        return await self.client.download_media(media, path)

    async def message_send(self, message, user_id, reply=None):
        sent = await self.client.send_message(self.dialogs[user_id].entity, message, reply_to=reply)
        await self.client.send_read_acknowledge(self.dialogs[user_id].entity, max_id=sent.id)
        new_messages = await self.client.get_messages(self.dialogs[user_id].entity, min_id=sent.id - 1)

        for msg in reversed(new_messages):
            self.messages[user_id].insert(0, msg)

        self.messages[user_id].sort(key=lambda x: x.id, reverse=True)
        self.remove_duplicates(self.messages[user_id])

    async def file_send(self, file, user_id, func):
        data = await self.client.send_file(self.dialogs[user_id].entity, file, progress_callback=func)
        new_messages = await self.client.get_messages(self.dialogs[user_id].entity, min_id=data.id - 1)

        for msg in reversed(new_messages):
            self.messages[user_id].insert(0, msg)

        self.messages[user_id].sort(key=lambda x: x.id, reverse=True)
        self.remove_duplicates(self.messages[user_id])

    async def read_all_messages(self, user_id):
        if self.messages[user_id] and hasattr(self.messages[user_id][0], 'id'):
            await self.client.send_read_acknowledge(self.dialogs[user_id].entity,
                                                    max_id=self.messages[user_id][0].id)

    def remove_duplicates(self, messages):
        seen = set()
        unique = []
        for msg in messages:
            if msg.id not in seen:
                seen.add(msg.id)
                unique.append(msg)
        messages.clear()
        messages.extend(unique)
        return messages


# Singleton instance (to be initialized with await)
client = TelegramApi()
